#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "build-linux.sh must run on Linux (current: $(uname -s))" >&2
  exit 1
fi

python3 -m pip install -q -e ".[build]"
exec python3 "$ROOT/scripts/build-binary.py" --platform linux "$@"
