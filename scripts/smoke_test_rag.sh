#!/usr/bin/env bash
# Smoke test: verify RAG search returns non-flat scores (i.e. sentence_transformers embedder is active).
# Usage: bash scripts/smoke_test_rag.sh [retrieval_url]
set -euo pipefail

URL="${1:-http://localhost:8001}"

echo "=== Smoke test: checking that RAG scores are not flat ==="

# Query 1
RESP1=$(curl -sf "${URL}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "как подключиться к Termidesk", "top_k": 5}')

# Query 2 (different topic)
RESP2=$(curl -sf "${URL}/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "ошибка черный экран после входа", "top_k": 5}')

# Extract scores and check uniqueness
python3 - "$RESP1" "$RESP2" <<'PYEOF'
import json, sys

def check(label, raw):
    data = json.loads(raw)
    results = data.get("results", [])
    if not results:
        print(f"  [{label}] WARNING: no results returned -- is knowledge ingested?")
        return False
    scores = [round(r.get("score", 0), 6) for r in results]
    unique = len(set(scores))
    print(f"  [{label}] scores={scores}  unique={unique}")
    if unique <= 1 and len(scores) > 1:
        print(f"  [{label}] FAIL: all scores identical -- embedder is likely mock")
        return False
    print(f"  [{label}] OK")
    return True

ok1 = check("query1", sys.argv[1])
ok2 = check("query2", sys.argv[2])

if ok1 and ok2:
    print("\n=== PASS: RAG scores are differentiated ===")
    sys.exit(0)
else:
    print("\n=== FAIL: RAG scores are flat or empty ===")
    sys.exit(1)
PYEOF
