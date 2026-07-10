#!/bin/sh
# Bumps the MarkItDown pin in requirements-markitdown.txt to the latest
# version published on PyPI. Does NOT rebuild the image — review the diff,
# then run `docker compose up --build` yourself once you're happy with it.
#
# Usage: bash scripts/update_markitdown.sh

set -e

REQ_FILE="$(dirname "$0")/../requirements-markitdown.txt"

LATEST=$(curl -fsSL https://pypi.org/pypi/markitdown/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])")

if [ -z "$LATEST" ]; then
  echo "Could not determine the latest MarkItDown version from PyPI." >&2
  exit 1
fi

CURRENT=$(grep -oE '==[0-9][^"[:space:]]*' "$REQ_FILE" | head -1 | tr -d '=')

echo "Current pin: ${CURRENT:-unknown}"
echo "Latest on PyPI: $LATEST"

if [ "$CURRENT" = "$LATEST" ]; then
  echo "Already up to date."
  exit 0
fi

sed -i.bak -E "s/==[0-9][^\"[:space:]]*/==${LATEST}/" "$REQ_FILE"
rm -f "${REQ_FILE}.bak"

echo
echo "Updated ${REQ_FILE}:"
grep '^markitdown' "$REQ_FILE"
echo
echo "Next steps:"
echo "  1. Review the change above (and MarkItDown's changelog for breaking changes)."
echo "  2. Rebuild: docker compose up --build"
echo "  3. Run: pytest  (validates the key formats still convert correctly)"
