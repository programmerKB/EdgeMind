FROM python:3.11.16-slim-trixie@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# UID 1000 matches the default local developer account and keeps bind-mounted
# source and generated reports writable without running the application as root.
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --create-home --shell /usr/sbin/nologin app \
    && python -m venv "$VIRTUAL_ENV" \
    && chown -R app:app /app "$VIRTUAL_ENV"

COPY --chown=app:app requirements.txt .

USER app

# Install dependencies before source code so Docker can reuse this layer.
RUN uv pip install -r requirements.txt

# Development uses a source bind mount and reloads Python code on changes.
FROM dependencies AS development

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# Production ships application code in the image and only mounts report output.
FROM dependencies AS production

COPY --chown=app:app . .
RUN mkdir -p /app/outputs

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
