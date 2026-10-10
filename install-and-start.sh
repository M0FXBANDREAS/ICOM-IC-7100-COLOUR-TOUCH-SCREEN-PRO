#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bash install.sh
exec bash start-panel.sh "$@"
