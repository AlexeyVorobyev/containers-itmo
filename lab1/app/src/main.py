from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

DATA_FILE = Path(os.environ.get("ANNOUNCEMENTS_JSON", "resources/announcements.json"))
_FILE_LOCK = Lock()


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <meta http-equiv="refresh" content="60" />
  <title>Announcements Board</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; }
    .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 14px; margin: 12px 0; }
    .muted { color: #666; font-size: 0.92rem; }
    input, textarea { width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #ccc; box-sizing: border-box; }
    textarea { min-height: 90px; resize: vertical; }
    button { padding: 10px 14px; border-radius: 10px; border: 1px solid #333; background: #111; color: #fff; cursor: pointer; }
    button.secondary { background: #fff; color: #111; border: 1px solid #ccc; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 12px; max-width: 900px; }
    .top { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; border: 1px solid #ddd; font-size: 0.85rem; }
    .title { font-size: 1.05rem; font-weight: 650; margin: 0 0 6px 0; }
    .text { white-space: pre-wrap; margin: 0; }
    form { margin: 0; }
  </style>
</head>
<body>
  <div class="grid">
    <div class="top">
      <div>
        <h1 style="margin:0;">Announcements Board</h1>
        <div class="muted">Auto-refreshes every minute • Last render: {{ now_human }}</div>
      </div>
      <div class="row">
        <span class="badge">{{ items|length }} item(s)</span>
        <button class="secondary" onclick="window.location.reload()">Refresh now</button>
      </div>
    </div>

    <div class="card">
      <h2 style="margin:0 0 10px 0; font-size:1rem;">Add announcement</h2>
      <form method="post" action="{{ url_for('add_announcement') }}">
        <div style="margin-bottom:10px;">
          <label class="muted">Title</label>
          <input name="title" maxlength="140" required placeholder="Short title..." />
        </div>
        <div style="margin-bottom:10px;">
          <label class="muted">Text</label>
          <textarea name="text" maxlength="5000" required placeholder="Write your announcement..."></textarea>
        </div>
        <div class="row">
          <button type="submit">Add</button>
          <span class="muted">Tip: page refreshes automatically every 60s.</span>
        </div>
      </form>
    </div>

    {% if items %}
      {% for a in items %}
        <div class="card">
          <div class="title">{{ a.title }}</div>
          <div class="muted">{{ a.created_at_human }}</div>
          <p class="text">{{ a.text }}</p>
        </div>
      {% endfor %}
    {% else %}
      <div class="card">
        <div class="muted">No announcements yet. Add the first one above.</div>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def human_time(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception:
        return iso_str
    return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def ensure_data_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        atomic_write_json(path, [])


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass


def read_announcements(path: Path) -> List[Dict[str, Any]]:
    ensure_data_file(path)
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except json.JSONDecodeError:
        # Corrupt file: keep a backup and reset
        backup = path.with_suffix(path.suffix + ".corrupt")
        try:
            os.replace(path, backup)
        except Exception:
            pass
        atomic_write_json(path, [])
    except FileNotFoundError:
        atomic_write_json(path, [])
    return []


def write_announcements(path: Path, items: List[Dict[str, Any]]) -> None:
    atomic_write_json(path, items)


def normalize_text(value: Any, max_len: int) -> str:
    s = ("" if value is None else str(value)).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def create_announcement(title: str, text: str) -> Dict[str, Any]:
    return {
        "id": f"ann_{datetime.now(timezone.utc).timestamp():.6f}".replace(".", "_"),
        "title": title,
        "text": text,
        "created_at": now_utc_iso(),
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/healthcheck")
    def healthcheck():
        return jsonify(
            {
                "ok": True,
            }
        ), 200

    @app.get("/")
    def index():
        with _FILE_LOCK:
            items = read_announcements(DATA_FILE)

        items_sorted = sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)

        view_items = []
        for a in items_sorted:
            view_items.append(
                {
                    "id": a.get("id", ""),
                    "title": a.get("title", ""),
                    "text": a.get("text", ""),
                    "created_at": a.get("created_at", ""),
                    "created_at_human": human_time(a.get("created_at", "")),
                }
            )

        return render_template_string(
            HTML_TEMPLATE,
            items=view_items,
            now_human=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    @app.post("/add")
    def add_announcement():
        payload: Dict[str, Any] = {}
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict()

        title = normalize_text(payload.get("title"), max_len=140)
        text = normalize_text(payload.get("text"), max_len=5000)

        if not title or not text:
            return jsonify({"ok": False, "error": "Both 'title' and 'text' are required."}), 400

        new_item = create_announcement(title, text)

        with _FILE_LOCK:
            items = read_announcements(DATA_FILE)
            items.append(new_item)
            write_announcements(DATA_FILE, items)

        if not request.is_json:
            return redirect(url_for("index"))

        return jsonify({"ok": True, "item": new_item}), 201

    return app


def main() -> None:
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
