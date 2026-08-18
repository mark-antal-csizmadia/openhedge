#!/usr/bin/env bash
# Print points_count for the Qdrant markets collection.
set -euo pipefail

QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-markets}"
URL="${QDRANT_URL%/}/collections/${COLLECTION}"

body="$(mktemp)"
trap 'rm -f "$body"' EXIT

http_code="$(curl -sS -o "$body" -w "%{http_code}" "$URL")" || {
  echo "error: could not reach Qdrant at ${QDRANT_URL}" >&2
  exit 1
}

if [[ "$http_code" != "200" ]]; then
  echo "error: collection '${COLLECTION}' not found at ${URL} (HTTP ${http_code})" >&2
  cat "$body" >&2
  echo >&2
  exit 1
fi

python3 -c '
import json, sys
data = json.load(sys.stdin)
result = data.get("result") or {}
if "points_count" not in result:
    print("error: response missing result.points_count", file=sys.stderr)
    sys.exit(1)
print(int(result["points_count"]))
' <"$body"
