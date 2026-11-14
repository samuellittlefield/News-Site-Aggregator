#!/bin/zsh
# Example .mini/setup.sh for News-Site-Aggregator. Copy to <repo>/.mini/setup.sh and chmod +x.
set -euo pipefail

# Start Postgres if it isn't up. The mini is headless, so start the server directly
# rather than launching the Postgres.app GUI. Paths are Postgres.app's defaults for v16;
# verify them on the mini.
PG_BIN="/Applications/Postgres.app/Contents/Versions/16/bin"
PG_DATA="$HOME/Library/Application Support/Postgres/var-16"
if ! "$PG_BIN/pg_isready" -q; then
  "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$PG_DATA/postgres.log" start -w
fi

cd backend
[[ -d .venv ]] || python3.11 -m venv .venv
.venv/bin/pip install -q -r requirements.txt -r requirements-dev.txt
