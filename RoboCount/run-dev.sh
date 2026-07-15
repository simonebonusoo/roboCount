#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
PIP_BIN="$VENV_DIR/bin/pip"
ENV_FILE="$ROOT_DIR/.env"
REQUIREMENTS_FILE="$ROOT_DIR/requirements.txt"
DEV_REQUIREMENTS_FILE="$ROOT_DIR/requirements-dev.txt"
PYTHON_MARKER="$VENV_DIR/.requirements.sha256"
NODE_MODULES_DIR="$ROOT_DIR/node_modules"
NODE_LOCKFILE="$ROOT_DIR/package-lock.json"
NODE_MARKER="$NODE_MODULES_DIR/.package-lock.json"

BACKEND_PID=""
FRONTEND_PID=""
SHUTDOWN_DONE=0

log() {
  printf '[run-dev] %s\n' "$1"
}

fail() {
  printf '[run-dev] Errore: %s\n' "$1" >&2
  exit 1
}

stop_process() {
  local pid="${1:-}"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
}

backend_healthcheck() {
  "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from urllib.request import urlopen

with urlopen("http://127.0.0.1:8000/api/health", timeout=2) as response:
    raise SystemExit(0 if response.status == 200 else 1)
PY
}

shutdown_processes() {
  if [ "$SHUTDOWN_DONE" -eq 1 ]; then
    return
  fi
  SHUTDOWN_DONE=1
  log "Arresto server di sviluppo..."
  stop_process "$BACKEND_PID"
  stop_process "$FRONTEND_PID"
}

on_signal() {
  printf '\n'
  log "Segnale ricevuto, chiusura in corso..."
  shutdown_processes
  exit 130
}

on_exit() {
  local status=$?
  shutdown_processes
  exit "$status"
}

trap on_signal INT TERM
trap on_exit EXIT

command -v python3 >/dev/null 2>&1 || fail "python3 non trovato nel PATH."
command -v npm >/dev/null 2>&1 || fail "npm non trovato nel PATH."

if [ ! -x "$PYTHON_BIN" ]; then
  log "Creo il virtual environment locale in .venv..."
  python3 -m venv "$VENV_DIR"
fi

if [ ! -f "$REQUIREMENTS_FILE" ]; then
  fail "requirements.txt non trovato."
fi
if [ ! -f "$DEV_REQUIREMENTS_FILE" ]; then
  fail "requirements-dev.txt non trovato."
fi

REQUIREMENTS_HASH="$(
  shasum -a 256 "$REQUIREMENTS_FILE" "$DEV_REQUIREMENTS_FILE" | shasum -a 256 | awk '{print $1}'
)"

NEED_PYTHON_INSTALL=0
if [ ! -f "$PYTHON_MARKER" ] || [ "$(cat "$PYTHON_MARKER" 2>/dev/null || true)" != "$REQUIREMENTS_HASH" ]; then
  NEED_PYTHON_INSTALL=1
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn, psycopg, psycopg_pool" >/dev/null 2>&1; then
  NEED_PYTHON_INSTALL=1
fi

if [ "$NEED_PYTHON_INSTALL" -eq 1 ]; then
  log "Installo o aggiorno le dipendenze Python della .venv..."
  "$PIP_BIN" install -r "$DEV_REQUIREMENTS_FILE"
  printf '%s' "$REQUIREMENTS_HASH" > "$PYTHON_MARKER"
fi

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$ROOT_DIR/.env.save" ]; then
    fail "File .env mancante nella root del progetto. E presente .env.save: copialo in .env e verifica che la variabile si chiami DATABASE_URL (non PYDATABASE_URL)."
  fi
  fail "File .env mancante nella root del progetto. Crea .env partendo da .env.example."
fi

log "Verifico la configurazione locale..."
"$PYTHON_BIN" - <<'PY'
from backend.config import ConfigError, format_database_target, get_runtime_config

try:
    config = get_runtime_config(require_database=True, require_session_secret=True)
except ConfigError as exc:
    raise SystemExit(f"Configurazione non valida: {exc}") from None

if config.database_target is None:
    raise SystemExit("Configurazione non valida: DATABASE_URL mancante.")

print(f"[run-dev] Database target validato: {format_database_target(config.database_target)}")
print("[run-dev] SESSION_SECRET presente.")
PY

NEED_NODE_INSTALL=0
if [ ! -d "$NODE_MODULES_DIR" ] || [ ! -f "$NODE_MARKER" ] || [ "$NODE_LOCKFILE" -nt "$NODE_MARKER" ]; then
  NEED_NODE_INSTALL=1
fi

if ! npm exec -- vite --version >/dev/null 2>&1; then
  NEED_NODE_INSTALL=1
fi

if [ "$NEED_NODE_INSTALL" -eq 1 ]; then
  log "Installo o aggiorno le dipendenze frontend..."
  npm install --no-fund --no-audit
fi

if [ -d "$NODE_MODULES_DIR/.vite" ]; then
  rm -rf "$NODE_MODULES_DIR/.vite"
fi

if [ -d "$ROOT_DIR/dist" ]; then
  rm -rf "$ROOT_DIR/dist"
fi

log "Avvio backend FastAPI su http://127.0.0.1:8000"
"$PYTHON_BIN" -m uvicorn api.index:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

BACKEND_READY=0
for _ in $(seq 1 15); do
  if backend_healthcheck; then
    BACKEND_READY=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" || true
    fail "Il backend e terminato durante l'avvio. Controlla l'errore mostrato sopra."
  fi
  sleep 1
done

if [ "$BACKEND_READY" -ne 1 ]; then
  fail "Il backend non ha completato lo startup o non risponde su /api/health."
fi

log "Avvio frontend Vite su http://127.0.0.1:5173"
npm run dev &
FRONTEND_PID=$!

sleep 2
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  wait "$FRONTEND_PID" || true
  fail "Il frontend e terminato durante l'avvio. Controlla l'errore mostrato sopra."
fi

printf '\n'
log "RoboCount e avviato. Premi Ctrl+C per fermare backend e frontend."

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID" || BACKEND_STATUS=$?
    BACKEND_STATUS="${BACKEND_STATUS:-1}"
    log "Il backend si e arrestato con codice ${BACKEND_STATUS}. Chiudo anche il frontend."
    shutdown_processes
    exit "$BACKEND_STATUS"
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    wait "$FRONTEND_PID" || FRONTEND_STATUS=$?
    FRONTEND_STATUS="${FRONTEND_STATUS:-1}"
    log "Il frontend si e arrestato con codice ${FRONTEND_STATUS}. Chiudo anche il backend."
    shutdown_processes
    exit "$FRONTEND_STATUS"
  fi

  sleep 1
done
