# Termidesk VDI Support Bot

Telegram-бот чат-поддержки для Termidesk VDI с RAG (Retrieval-Augmented Generation) и локальной/подменяемой LLM.

## Архитектура

- **tg-bot-service** — приём апдейтов Telegram (long polling), проксирование в orchestrator
- **orchestrator-service** — API gateway: диалог, вызов retrieval + LLM, формирование ответа
- **retrieval-service** — поиск по базе знаний (pgvector / text search)
- **llm-service** — единый интерфейс к LLM (локальный HTTP endpoint или mock)
- **ingest-service** — загрузка и обновление базы знаний (md/pdf/txt)

## Быстрый старт

```bash
cp .env.example .env
# Заполните TELEGRAM_BOT_TOKEN в .env

make migrate   # применить миграции БД (один раз)
make up        # или: docker compose up -d
```

После запуска напишите боту в Telegram — ответ идёт через mock LLM и простой retrieval. Для ответов по базе знаний сначала выполните `make ingest`.

## Добавление документов в базу знаний

Положите файлы (`.md`, `.txt`, `.pdf`) в `knowledge/termidesk/`, затем:

```bash
make ingest
# или: docker compose --profile tools run --rm ingest
```

## Метрики и здоровье

- Метрики Prometheus: `GET /metrics` на каждом сервисе (порты см. в docker-compose).
- Health: `GET /healthz` (liveness), `GET /readyz` (readiness).

Пример проверки после запуска:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/metrics
```

## Примеры запросов к API

### Orchestrator (чат)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "tg_123", "message": "Как настроить Termidesk?", "conversation_id": null}'
```

### Retrieval (поиск)

```bash
curl -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "ошибка подключения", "top_k": 5}'
```

### LLM (генерация, при LLM_MOCK=false)

```bash
curl -X POST http://localhost:8002/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Ответь кратко: что такое Termidesk?", "max_tokens": 128}'
```

## Структура репозитория

- `shared/` — общая библиотека (config, logging, http client, schemas)
- `services/tg_bot/` — Telegram-бот (aiogram)
- `services/orchestrator/` — оркестратор диалога
- `services/retrieval/` — поиск по базе знаний
- `services/llm/` — клиент к LLM
- `services/ingest/` — инжест документов
- `knowledge/termidesk/` — база знаний (md/txt/pdf)

## Команды Makefile

- `make up` — поднять все сервисы
- `make down` — остановить
- `make logs` — логи
- `make migrate` — применить миграции
- `make test` — запуск тестов
- `make format` — форматирование кода
