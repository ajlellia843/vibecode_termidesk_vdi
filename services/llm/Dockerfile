FROM python:3.11-slim

WORKDIR /app

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

COPY services/llm/pyproject.toml /app/services/llm/
RUN pip install --no-cache-dir -e /app/services/llm

COPY services/llm /app/services/llm
ENV PYTHONPATH=/app/services/llm/src

WORKDIR /app/services/llm
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "llm.main:app", "--host", "0.0.0.0", "--port", "8002"]
