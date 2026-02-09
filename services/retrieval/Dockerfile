FROM python:3.11-slim

WORKDIR /app

# shared package
COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

COPY services/retrieval/pyproject.toml /app/services/retrieval/
RUN pip install --no-cache-dir -e /app/services/retrieval

COPY services/retrieval /app/services/retrieval
ENV PYTHONPATH=/app/services/retrieval/src

WORKDIR /app/services/retrieval
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "retrieval.main:app", "--host", "0.0.0.0", "--port", "8001"]
