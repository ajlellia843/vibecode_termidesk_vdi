FROM python:3.11-slim

WORKDIR /app

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

COPY services/orchestrator/pyproject.toml /app/services/orchestrator/
RUN pip install --no-cache-dir -e /app/services/orchestrator

COPY services/orchestrator /app/services/orchestrator
ENV PYTHONPATH=/app/services/orchestrator/src

WORKDIR /app/services/orchestrator
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
