#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo 'First-time setup: bash install-and-start.sh' >&2
  exit 1
fi
exec .venv/bin/python server.py "$@"
