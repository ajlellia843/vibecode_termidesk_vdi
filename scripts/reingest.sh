#!/usr/bin/env bash
set -euo pipefail

echo "=== Truncating retrieval.documents and retrieval.chunks ==="
docker compose exec postgres psql -U "${POSTGRES_USER:-app}" -d "${POSTGRES_DB:-termidesk_bot}" \
  -c "TRUNCATE retrieval.documents CASCADE;"

echo "=== Running ingest ==="
docker compose --profile tools run --rm ingest

echo "=== Done ==="
echo "Verify with:"
echo "  curl -s http://localhost:8001/search -d '{\"query\":\"test\",\"top_k\":3}' -H 'Content-Type: application/json' | python -m json.tool"
