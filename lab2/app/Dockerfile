FROM python:3.13-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates

ADD https://astral.sh/uv/0.9.15/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

ENV PATH="/root/.local/bin/:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --locked


FROM python:3.13-slim AS final

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --chown=appuser:appuser --from=builder /app/.venv .venv
COPY --chown=appuser:appuser src/ src/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/healthcheck || exit 1

USER appuser

CMD ["python", "-m", "src.main"]
