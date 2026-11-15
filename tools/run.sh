#!/usr/bin/env bash
# Local runs with the same pinned fonttools and brotli as the Action (tools/requirements.txt).
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --no-project --with fonttools==4.67.0 --with brotli==1.2.0 python tools/build.py "$@"
