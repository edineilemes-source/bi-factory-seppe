#!/usr/bin/env bash
# Inicializador nao destrutivo do BI Factory SEPPE para Codespaces.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${TMPDIR:-/tmp}/bi-factory-seppe-logs"
mkdir -p "$LOG_DIR"

is_listening() {
  python3 - "$1" <<'PY'
import socket,sys
s=socket.socket()
s.settimeout(1)
try:
    s.connect(("127.0.0.1",int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}
wait_http() {
  local url="$1"
  for i in $(seq 1 30); do
    if curl --silent --fail --max-time 2 -o /dev/null "$url"; then return 0; fi
    sleep 1
  done
  return 1
}

if is_listening 8505; then
  echo "8505 ja ocupada; nao iniciaremos outro processo."
else
  echo "Iniciando API 8505..."
  (cd "$ROOT" && nohup python3 -u scripts/serve_bi_factory_api.py --port 8505 > "$LOG_DIR/api-8505.log" 2>&1 < /dev/null &)
fi

if ! wait_http "http://127.0.0.1:8505/api/overview"; then
  echo "ERRO: API nao respondeu HTTP 2xx. Consulte $LOG_DIR/api-8505.log" >&2
  exit 1
fi

if is_listening 8506; then
  echo "8506 ja ocupada; nao iniciaremos outro processo."
else
  if [[ ! -x "$ROOT/web/bi_factory/node_modules/.bin/vite" ]]; then
    echo "ERRO: dependencias Vite ausentes; execute npm ci em web/bi_factory." >&2
    exit 1
  fi
  echo "Iniciando frontend 8506..."
  (cd "$ROOT/web/bi_factory" && nohup ./node_modules/.bin/vite --host 0.0.0.0 --port 8506 --strictPort > "$LOG_DIR/vite-8506.log" 2>&1 < /dev/null &)
fi

for path in / /api/overview /visual-editor/index.html /echarts-studio.html; do
  if wait_http "http://127.0.0.1:8506$path"; then
    echo "OK 8506$path"
  else
    echo "ERRO 8506$path; consulte $LOG_DIR/vite-8506.log" >&2
    exit 1
  fi
done
echo "Ambiente local pronto. Abra a porta 8506 na aba PORTS do Codespaces."
echo "Logs: $LOG_DIR"
