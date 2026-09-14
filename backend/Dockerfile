FROM python:3.12-slim

WORKDIR /app
ARG UV_VERSION=0.11.27
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/incident_lens ./incident_lens
COPY backend/migrations ./migrations
COPY data/knowledge /data/knowledge
RUN pip install --no-cache-dir "uv==${UV_VERSION}" \
    && uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# The API does not need root and receives all credentials at runtime.
RUN addgroup --system --gid 10001 incident-lens \
    && adduser --system --uid 10001 --gid 10001 --no-create-home incident-lens \
    && chown -R incident-lens:incident-lens /app
USER 10001:10001

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"
