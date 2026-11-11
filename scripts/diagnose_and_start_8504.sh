#!/usr/bin/env bash
# Diagnóstico e retomada não destrutiva do BI Factory.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOGDIR="${TMPDIR:-/tmp}/bi-factory-seppe"
mkdir -p "$LOGDIR"
check(){ curl --noproxy '*' -fsS --max-time 4 "$1" >/dev/null 2>&1; }
probe(){ local name="$1" url="$2"; if check "$url"; then echo "PASS $name $url"; else echo "FAIL $name $url"; fi; }
start_if_free(){
 local port="$1" name="$2"; shift 2
 if check "http://127.0.0.1:$port/"; then echo "PASS $name existente na porta $port"; return; fi
 # Porta ocupada por processo estranho ou serviço travado: não matar nada automaticamente.
 if python3 - "$port" <<'PY'
import socket,sys
s=socket.socket();s.settimeout(1)
try: sys.exit(0 if s.connect_ex(('127.0.0.1',int(sys.argv[1])))==0 else 1)
finally:s.close()
PY
 then
   echo "BLOCKED $name: porta $port ocupada mas sem HTTP saudável; processo preservado." >&2
   return 1
 fi
 echo "START $name porta $port"
 nohup "$@" >"$LOGDIR/$name.log" 2>&1 </dev/null &
 local i
 for i in $(seq 1 25); do
   if check "http://127.0.0.1:$port/"; then echo "PASS $name iniciou"; return; fi
   sleep 1
 done
 echo "FAIL $name não respondeu; log $LOGDIR/$name.log" >&2
 return 1
}
echo "=== DIAGNÓSTICO LOCAL (sem encerrar processos ou alterar dados) ==="
echo "BRANCH: $(git branch --show-current)"
echo "COMMIT: $(git rev-parse --short HEAD)"
git status --short | head -n 30
probe "API 8505" "http://127.0.0.1:8505/api/products"
probe "UI 8504" "http://127.0.0.1:8504/"
probe "PROXY API" "http://127.0.0.1:8504/api/overview"
probe "EDITOR" "http://127.0.0.1:8504/visual-editor/index.html"
probe "ECHARTS" "http://127.0.0.1:8504/echarts-studio.html"
if [[ "${1:-}" != "--start" ]]; then
 echo "Somente diagnóstico. Use --start para iniciar serviços ausentes sem matar processos."
 exit 0
fi
start_if_free 8505 api-8505 python3 -u scripts/serve_bi_factory_api.py --port 8505 || true
if [[ ! -x web/bi_factory/node_modules/.bin/vite ]]; then
 echo "BLOCKED Vite: dependências não instaladas; não alterei node_modules." >&2
else
 start_if_free 8504 vite-8504 "$ROOT/web/bi_factory/node_modules/.bin/vite" --config "$ROOT/web/bi_factory/vite.config.js" --root "$ROOT/web/bi_factory" --host 0.0.0.0 --port 8504 --strictPort || true
fi
echo "=== VERIFICAÇÃO FINAL ==="
probe "API" "http://127.0.0.1:8505/api/products"
probe "UI" "http://127.0.0.1:8504/"
probe "PROXY" "http://127.0.0.1:8504/api/overview"
probe "EDITOR" "http://127.0.0.1:8504/visual-editor/index.html"
probe "ECHARTS" "http://127.0.0.1:8504/echarts-studio.html"
echo "LOGS: $LOGDIR"
