#!/usr/bin/env bash
# A private, GPU-enabled Ollama for FinPulse that needs no root and no system package.
#
#   scripts/ollama-local.sh setup     copy the binary and the CUDA 13 runner out of the ollama/ollama image
#   scripts/ollama-local.sh start     serve on 127.0.0.1:11435 with one model on the GPU at a time
#   scripts/ollama-local.sh pull      pull the two models the pipeline uses
#   scripts/ollama-local.sh status | stop | logs
#
# Why not the Docker image itself: Docker here has no NVIDIA runtime, so a container would run on
# the CPU. The binary runs on the host driver directly. Another Ollama may already own :11434, so
# this one uses :11435 (FINPULSE_OLLAMA_URL in server/.env points the API at it).
set -euo pipefail

HOME_DIR="${FINPULSE_OLLAMA_HOME:-$HOME/.local/opt/finpulse-ollama}"
MODELS_DIR="${FINPULSE_OLLAMA_MODELS:-$HOME/.local/share/finpulse-ollama/models}"
STATE_DIR="${FINPULSE_OLLAMA_STATE:-$HOME/.local/state/finpulse}"
HOST="${FINPULSE_OLLAMA_HOST:-127.0.0.1:11435}"
IMAGE="${FINPULSE_OLLAMA_IMAGE:-ollama/ollama:latest}"
BIN="$HOME_DIR/bin/ollama"
PIDFILE="$STATE_DIR/ollama.pid"
LOG="$STATE_DIR/ollama.log"
MODELS=(qwen2.5:7b-instruct llama3.1:8b-instruct-q4_K_M)

setup() {
  [[ -x "$BIN" ]] && { echo "already set up: $BIN"; return; }
  command -v docker >/dev/null || { echo "docker is needed once, to copy the binary out of $IMAGE" >&2; exit 1; }
  mkdir -p "$HOME_DIR/bin" "$HOME_DIR/lib/ollama"
  local cid; cid=$(docker create "$IMAGE")
  trap 'docker rm "$cid" >/dev/null' EXIT
  docker cp "$cid:/usr/bin/ollama" "$BIN"
  # shared libraries and the llama.cpp helpers at the top level, plus the CUDA 13 runner (RTX 50 series)
  local f
  for f in $(docker run --rm --entrypoint /bin/sh "$IMAGE" -c 'ls /usr/lib/ollama | grep -E "\.so|llama-server|llama-quantize"'); do
    docker cp "$cid:/usr/lib/ollama/$f" "$HOME_DIR/lib/ollama/$f"
  done
  docker cp "$cid:/usr/lib/ollama/cuda_v13" "$HOME_DIR/lib/ollama/cuda_v13"
  echo "installed $("$BIN" --version 2>&1 | tail -1) in $HOME_DIR"
}

running() { [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

start() {
  [[ -x "$BIN" ]] || setup
  running && { echo "already running (pid $(cat "$PIDFILE")) on $HOST"; return; }
  mkdir -p "$MODELS_DIR" "$STATE_DIR"
  OLLAMA_HOST="$HOST" OLLAMA_MODELS="$MODELS_DIR" \
  OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 \
  OLLAMA_KV_CACHE_TYPE=q8_0 OLLAMA_KEEP_ALIVE=10m \
    nohup "$BIN" serve >"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  for _ in $(seq 1 30); do
    curl -fs "http://$HOST/api/version" >/dev/null && { echo "serving on $HOST (pid $(cat "$PIDFILE"))"; return; }
    sleep 0.5
  done
  echo "did not come up; see $LOG" >&2; exit 1
}

stop() { running && { kill "$(cat "$PIDFILE")"; rm -f "$PIDFILE"; echo stopped; } || echo "not running"; }

pull() {
  start
  local m
  for m in "${MODELS[@]}"; do OLLAMA_HOST="$HOST" "$BIN" pull "$m"; done
}

status() {
  running && echo "running (pid $(cat "$PIDFILE")) on $HOST" || echo "not running"
  curl -fs "http://$HOST/api/tags" 2>/dev/null | python3 -c 'import json,sys; [print("  ", m["name"], round(m["size"]/1e9,1), "GB") for m in json.load(sys.stdin)["models"]]' || true
}

case "${1:-status}" in
  setup) setup ;; start) start ;; stop) stop ;; pull) pull ;; status) status ;;
  logs) tail -n 50 "$LOG" ;;
  *) echo "usage: $0 setup|start|stop|pull|status|logs" >&2; exit 2 ;;
esac
