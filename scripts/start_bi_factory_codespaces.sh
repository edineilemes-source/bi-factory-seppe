#!/usr/bin/env bash
# Non-destructive Codespaces starter. Start detached processes and verify HTTP.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${TMPDIR:-/tmp}/bi-factory-seppe-logs"
mkdir -p "$LOG_DIR"
is_listening() {
  python3 - "$1" <<'PY'
import socket,sys
s=socket.socket();s.settimeout(1)
try: s.connect(("127.0.0.1",int(sys.argv[1])))
except OSError: sys.exit(1)
finally: s.close()
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
if ! is_listening 8505; then
  echo "Starting API 8505"
  cd "$ROOT"
  setsid -f python3 -u scripts/serve_bi_factory_api.py --port 8505 > "$LOG_DIR/api-8505.log" 2>&1 < /dev/null
fi
wait_http "http://127.0.0.1:8505/api/overview" || { echo "API 8505 HTTP failed: $LOG_DIR/api-8505.log" >&2; exit 1; }
if ! is_listening 8507; then
  command -v node >/dev/null || { echo "Node.js missing from PATH" >&2; exit 1; }
  test -x "$ROOT/web/bi_factory/node_modules/.bin/vite" || { echo "Vite missing" >&2; exit 1; }
  echo "Starting BI Factory OFICIAL Vite 8507"
  cd "$ROOT/web/bi_factory"
  setsid -f ./node_modules/.bin/vite --host 0.0.0.0 --port 8507 --strictPort > "$LOG_DIR/vite-8507.log" 2>&1 < /dev/null
fi
for path in / /api/overview /visual-editor/official-8507/index.html /api/products /api/fiscal; do
  wait_http "http://127.0.0.1:8507$path" || { echo "HTTP failure 8506$path: $LOG_DIR/vite-8507.log" >&2; exit 1; }
  echo "OK 8507$path"
done
echo "BI Factory oficial na porta 8507: catálogo e editor 8507 integrado. Verificação externa pelo navegador ainda necessária."
