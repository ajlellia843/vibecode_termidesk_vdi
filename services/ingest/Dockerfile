FROM python:3.11-slim

WORKDIR /app

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

COPY services/ingest/pyproject.toml /app/services/ingest/
RUN pip install --no-cache-dir -e /app/services/ingest

COPY services/ingest /app/services/ingest
COPY knowledge /app/knowledge
ENV PYTHONPATH=/app/services/ingest/src
ENV INGEST_KNOWLEDGE_PATH=/app/knowledge

WORKDIR /app/services/ingest
CMD ["python", "-m", "ingest.main"]
