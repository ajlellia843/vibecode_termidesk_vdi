FROM python:3.11-slim

WORKDIR /app

# shared (sentence-transformers). CPU-only PyTorch — быстрая сборка, меньше места.
# Для GPU раскомментировать блок ниже и закомментировать две строки RUN под этим комментарием.
COPY shared /app/shared
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -e /app/shared
# GPU (CUDA): предустановку torch не делать, тогда pip подтянет PyTorch с CUDA при установке shared:
# RUN pip install --no-cache-dir -e /app/shared

COPY services/ingest/pyproject.toml /app/services/ingest/
RUN pip install --no-cache-dir -e /app/services/ingest

COPY services/ingest /app/services/ingest
COPY knowledge /app/knowledge
ENV PYTHONPATH=/app/services/ingest/src
ENV INGEST_KNOWLEDGE_PATH=/app/knowledge

WORKDIR /app/services/ingest
CMD ["python", "-m", "ingest.main"]
