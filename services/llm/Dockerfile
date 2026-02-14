FROM python:3.11-slim

WORKDIR /app

# shared (sentence-transformers). CPU-only PyTorch — быстрая сборка, меньше места.
# Для GPU раскомментировать блок ниже и закомментировать две строки RUN под этим комментарием.
COPY shared /app/shared
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -e /app/shared
# GPU (CUDA): предустановку torch не делать, тогда pip подтянет PyTorch с CUDA при установке shared:
# RUN pip install --no-cache-dir -e /app/shared

COPY services/llm/pyproject.toml /app/services/llm/
RUN pip install --no-cache-dir -e /app/services/llm

COPY services/llm /app/services/llm
ENV PYTHONPATH=/app/services/llm/src

WORKDIR /app/services/llm
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "llm.main:app", "--host", "0.0.0.0", "--port", "8002"]
