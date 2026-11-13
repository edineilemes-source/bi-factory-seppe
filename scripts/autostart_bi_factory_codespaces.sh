#!/usr/bin/env bash
# Non-destructive Codespaces startup. No git checkout, merge or data deletion.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG=/tmp/bi-factory-seppe-logs
mkdir -p "$LOG"
exec 9>/tmp/bi-factory-seppe-autostart.lock
flock -n 9 || exit 0
echo "[$(date -Is)] Codespaces autostart" >> "$LOG/autostart.log"
cd "$ROOT" || exit 1
if [[ ! -x web/bi_factory/node_modules/.bin/vite ]]; then
  echo "Installing missing frontend dependencies" >> "$LOG/autostart.log"
  (cd web/bi_factory && npm ci) >> "$LOG/autostart.log" 2>&1 || echo "npm ci failed" >> "$LOG/autostart.log"
fi
bash scripts/start_bi_factory_codespaces.sh >> "$LOG/autostart.log" 2>&1 || echo "BI Factory startup failed; see logs" >> "$LOG/autostart.log"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  if ! pgrep -f '[p]ython3.*scripts/bi_factory_github_agent.py' >/dev/null; then
    nohup python3 -u scripts/bi_factory_github_agent.py >> "$LOG/github-agent.log" 2>&1 < /dev/null &
    echo "GitHub agent started" >> "$LOG/autostart.log"
  fi
else
  echo "GitHub CLI not authenticated; application startup remains independent" >> "$LOG/autostart.log"
fi
