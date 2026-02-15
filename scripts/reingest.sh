#!/usr/bin/env bash
set -euo pipefail

POSTGRES_USER="${POSTGRES_USER:-app}"
POSTGRES_DB="${POSTGRES_DB:-termidesk_bot}"

echo "=== Ensuring postgres is running ==="
docker compose up -d postgres

echo "=== Waiting for postgres to be ready ==="
for i in $(seq 1 60); do
  if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" 2>/dev/null; then
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "ERROR: postgres did not become ready in time. Check: docker compose logs postgres"
    exit 1
  fi
  sleep 1
done

echo "=== Truncating retrieval.documents and retrieval.chunks ==="
docker compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "TRUNCATE retrieval.documents CASCADE;"

echo "=== Building ingest image (ensures UPSERT pipeline is used) ==="
docker compose --profile tools build ingest

echo "=== Running ingest ==="
docker compose --profile tools run --rm ingest

echo "=== Done ==="
echo "Verify with:"
echo "  curl -s http://localhost:8001/search -d '{\"query\":\"test\",\"top_k\":3}' -H 'Content-Type: application/json' | python -m json.tool"
