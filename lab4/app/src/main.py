from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_TABLE = "public.announcements"

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


def normalize_text(value: Any, max_len: int) -> str:
    s = ("" if value is None else str(value)).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def human_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception:
            return value
    return ""


def get_database_url() -> str:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_DSN")
    if dsn:
        return dsn

    host = os.environ.get("PGHOST", "localhost")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "postgres")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "postgres")

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def make_pool() -> pool.ThreadedConnectionPool:
    dsn = get_database_url()
    minconn = int(os.environ.get("PGPOOL_MIN", "1"))
    maxconn = int(os.environ.get("PGPOOL_MAX", "10"))
    return psycopg2.pool.ThreadedConnectionPool(minconn=minconn, maxconn=maxconn, dsn=dsn)


def fetch_announcements(conn, limit: int = 200) -> List[Dict[str, Any]]:
    sql = f"""
        SELECT id, title, text, created_at
        FROM {_TABLE}
        ORDER BY created_at DESC
        LIMIT %s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    return [dict(r) for r in rows]


def insert_announcement(conn, title: str, text: str) -> Dict[str, Any]:
    created_at = now_utc()

    # Сначала пробуем вставку БЕЗ id (если в таблице id имеет DEFAULT, например uuid/serial)
    sql_no_id = f"""
        INSERT INTO {_TABLE} (title, text, created_at)
        VALUES (%s, %s, %s)
        RETURNING id, title, text, created_at
    """
    sql_with_id = f"""
        INSERT INTO {_TABLE} (id, title, text, created_at)
        VALUES (%s, %s, %s, %s)
        RETURNING id, title, text, created_at
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        try:
            cur.execute(sql_no_id, (title, text, created_at))
        except psycopg2.Error:
            # Если у таблицы нет дефолта для id — используем свой id
            conn.rollback()
            gen_id = f"ann_{created_at.timestamp():.6f}".replace(".", "_")
            cur.execute(sql_with_id, (gen_id, title, text, created_at))

        row = cur.fetchone()
        conn.commit()

    return dict(row)


def create_app() -> Flask:
    app = Flask(__name__)

    db_pool = make_pool()

    @app.get("/healthcheck")
    def healthcheck():
        conn = db_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                _ = cur.fetchone()
            return jsonify({"ok": True}), 200
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 503
        finally:
            db_pool.putconn(conn)

    @app.get("/")
    def index():
        conn = db_pool.getconn()
        try:
            items = fetch_announcements(conn, limit=200)
        finally:
            db_pool.putconn(conn)

        view_items = [
            {
                "id": a.get("id", ""),
                "title": a.get("title", ""),
                "text": a.get("text", ""),
                "created_at": a.get("created_at", ""),
                "created_at_human": human_time(a.get("created_at")),
            }
            for a in items
        ]

        return render_template_string(
            HTML_TEMPLATE,
            items=view_items,
            now_human=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    @app.post("/add")
    def add_announcement():
        conn = db_pool.getconn()
        payload: Dict[str, Any]
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict()

        title = normalize_text(payload.get("title"), max_len=140)
        text = normalize_text(payload.get("text"), max_len=5000)

        if not title or not text:
            return jsonify({"ok": False, "error": "Both 'title' and 'text' are required."}), 400

        try:
            new_item = insert_announcement(conn, title=title, text=text)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
        finally:
            db_pool.putconn(conn)

        if not request.is_json:
            return redirect(url_for("index"))

        # чтобы формат был похож на старый JSON-вариант
        new_item_out = {
            **new_item,
            "created_at_human": human_time(new_item.get("created_at")),
        }
        return jsonify({"ok": True, "item": new_item_out}), 201

    return app


def main() -> None:
    app = create_app()
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)


if __name__ == "__main__":
    main()
