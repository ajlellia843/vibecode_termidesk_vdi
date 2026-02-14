FROM python:3.11-slim

WORKDIR /app

# shared (sentence-transformers). CPU-only PyTorch — быстрая сборка, меньше места.
# Для GPU раскомментировать блок ниже и закомментировать две строки RUN под этим комментарием.
COPY shared /app/shared
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -e /app/shared
# GPU (CUDA): предустановку torch не делать, тогда pip подтянет PyTorch с CUDA при установке shared:
# RUN pip install --no-cache-dir -e /app/shared

COPY services/tg_bot/pyproject.toml /app/services/tg_bot/
RUN pip install --no-cache-dir -e /app/services/tg_bot

COPY services/tg_bot /app/services/tg_bot
ENV PYTHONPATH=/app/services/tg_bot/src

WORKDIR /app/services/tg_bot
CMD ["python", "-m", "tg_bot.main"]
