#!/usr/bin/env bash
# The whole stack on this machine, for development and for the demo:
#
#   scripts/live.sh            database, local LLM server, API, job worker and the web app on real data
#   scripts/live.sh preview    the web app alone on the synthetic preview data (no backend needed)
#
# Ctrl-C stops everything this script started. API and worker logs are in data/logs/.
# Models are loaded from the local cache only (HF_HUB_OFFLINE), so a demo makes no network calls;
# set FINPULSE_ONLINE=1 on the first run, or after clearing the cache, to let them download.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${1:-}" == "preview" ]]; then
  cd web
  FINPULSE_PREVIEW=1 exec bun run dev
fi

[[ -z "${FINPULSE_ONLINE:-}" ]] && export HF_HUB_OFFLINE=1
export FINPULSE_PREVIEW=0
mkdir -p data/logs

docker compose -f infra/docker-compose.yml up -d --wait db
scripts/ollama-local.sh start
(cd server && uv run alembic upgrade head)

# stop the API, the worker and the web app together, grandchildren included: they share this process group
trap 'trap - EXIT INT TERM; kill 0' EXIT INT TERM
(cd server && exec uv run finpulse serve) >data/logs/api.log 2>&1 &
(cd server && exec uv run finpulse worker) >data/logs/worker.log 2>&1 &

for _ in $(seq 1 60); do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null && break
  sleep 1
done
curl -sf http://127.0.0.1:8000/api/health || { echo "the API did not come up; see data/logs/api.log" >&2; exit 1; }
echo
echo "API http://127.0.0.1:8000   web http://localhost:3000   logs data/logs/"
# in the background and waited on, so a plain TERM (not only Ctrl-C) reaches the trap and stops everything
(cd web && exec bun run dev) &
wait $!
