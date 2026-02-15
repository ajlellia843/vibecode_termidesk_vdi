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

make migrate   # применить миграции БД (orchestrator + retrieval), в т.ч. таблицу orchestrator.users для выбора версии
make up        # или: docker compose up -d
```

Если при нажатии кнопки выбора версии появляется «Ошибка сохранения», выполните `make migrate` и перезапустите сервисы.

После запуска напишите боту в Telegram — ответ идёт через mock LLM и простой retrieval. Для ответов по базе знаний сначала выполните `make ingest`. Orchestrator использует порог уверенности RAG (`ORCHESTRATOR_RAG_MIN_CONFIDENCE`, по умолчанию 0.30): при низкой уверенности поиска возвращается режим диагностики (уточняющие вопросы и рекомендации что собрать) без вызова LLM.

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

## Если бот не использует базу знаний (отвечает без контекста из faq.md и т.д.)

Убедитесь, что применены миграции retrieval и загружена база:

1. **Проверьте логи retrieval при старте** — при отсутствии таблиц появится предупреждение `retrieval_schema_missing` и подсказка команды.
2. **Примените миграции retrieval вручную** (из корня проекта):
   ```bash
   docker compose run --rm retrieval python -m alembic -c alembic.ini upgrade head
   ```
   Должно завершиться без ошибок. Если видите ошибку про extension `vector` (нет прав) — создайте расширение в БД под суперпользователем: `CREATE EXTENSION IF NOT EXISTS vector;`
3. **Загрузите документы:**
   ```bash
   make ingest
   ```
4. Перезапустите сервисы: `docker compose up -d`.

## После смены embedder'а -- переиндексация (reingest)

Если вы сменили embedder backend или модель (например, с mock на sentence_transformers), необходимо переиндексировать базу знаний, чтобы пересоздать все embeddings:

```bash
make reingest
# или вручную:
# bash scripts/reingest.sh
```

Эта команда очистит таблицы `retrieval.documents` и `retrieval.chunks` и запустит ingest заново.

## Проверка что RAG "не плоский"

1. Убедитесь, что embedder настроен на `sentence_transformers`:
   ```bash
   docker compose exec retrieval env | grep EMBEDDER
   # Ожидается: RETRIEVAL_EMBEDDER_BACKEND=sentence_transformers
   ```

2. Проверьте логи retrieval при старте -- должно быть:
   ```
   embedder_config  backend=sentence_transformers  model=sentence-transformers/all-MiniLM-L6-v2  dim=384
   ```
   Если видите `embedder_mock_mode` -- embedder в режиме mock, исправьте переменные окружения.

3. Сделайте поисковый запрос и убедитесь, что score/distance различаются:
   ```bash
   curl -s http://localhost:8001/search \
     -H "Content-Type: application/json" \
     -d '{"query": "ошибка подключения", "top_k": 5}' | python -m json.tool
   ```
   Ожидается: `score` и `distance` разные для разных результатов (не одинаковые ~0.5).

4. Автоматический smoke-test:
   ```bash
   bash scripts/smoke_test_rag.sh
   ```

## Команды Makefile

- `make up` — поднять все сервисы
- `make down` — остановить
- `make logs` — логи
- `make migrate` — применить миграции
- `make ingest` — загрузить базу знаний
- `make reingest` — очистить и переиндексировать базу знаний (после смены embedder'а)
- `make test` — запуск тестов
- `make format` — форматирование кода
