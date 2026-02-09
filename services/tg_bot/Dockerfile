FROM python:3.11-slim

WORKDIR /app

COPY shared /app/shared
RUN pip install --no-cache-dir -e /app/shared

COPY services/tg_bot/pyproject.toml /app/services/tg_bot/
RUN pip install --no-cache-dir -e /app/services/tg_bot

COPY services/tg_bot /app/services/tg_bot
ENV PYTHONPATH=/app/services/tg_bot/src

WORKDIR /app/services/tg_bot
CMD ["python", "-m", "tg_bot.main"]
