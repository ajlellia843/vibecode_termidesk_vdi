.PHONY: up down logs migrate test format ingest reingest

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose run --rm orchestrator python -m alembic -c alembic.ini upgrade head
	docker compose run --rm retrieval python -m alembic -c alembic.ini upgrade head

test:
	pip install -e ./shared pytest pytest-asyncio httpx
	pip install -e ./services/orchestrator && cd services/orchestrator && pytest tests -v && cd ../..
	pip install -e ./services/retrieval && cd services/retrieval && pytest tests -v && cd ../..
	pip install -e ./services/llm && cd services/llm && pytest tests -v && cd ../..

format:
	ruff format .
	ruff check . --fix
	black shared services

ingest:
	docker compose --profile tools run --rm ingest

reingest:
	bash scripts/reingest.sh
