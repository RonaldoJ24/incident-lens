FROM python:3.12-slim

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/incident_lens ./incident_lens
COPY backend/migrations ./migrations
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
