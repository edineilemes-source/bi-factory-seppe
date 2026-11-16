#!/usr/bin/env bash
# Persistent non-destructive Codespaces service monitor. Never changes Git branches.
set -uo pipefail
ROOT="${BI_FACTORY_ROOT:-/workspaces/bi-factory-seppe}"
LOG=/tmp/bi-factory-seppe-logs
mkdir -p "$LOG"
if [[ "${1:-}" != "--monitor" ]]; then
  echo "[$(date -Is)] Codespaces lifecycle hook invoked" >> "$LOG/autostart.log"
  # Spawn independently of the lifecycle hook's process group.
  setsid -f bash "$ROOT/scripts/autostart_bi_factory_codespaces.sh" --monitor >> "$LOG/monitor-launch.log" 2>&1 < /dev/null
  exit 0
fi
exec 9>/tmp/bi-factory-seppe-autostart.lock
flock -n 9 || exit 0
echo "[$(date -Is)] Persistent monitor started (PID $$)" >> "$LOG/autostart.log"
cd "$ROOT" || exit 1
while true; do
  if ! command -v node >/dev/null 2>&1; then
    echo "[$(date -Is)] Node.js missing; waiting" >> "$LOG/autostart.log"
  else
    if [[ ! -x web/bi_factory/node_modules/.bin/vite ]]; then
      echo "[$(date -Is)] Installing Vite dependencies" >> "$LOG/autostart.log"
      (cd web/bi_factory && npm ci) >> "$LOG/autostart.log" 2>&1 || echo "npm ci failed" >> "$LOG/autostart.log"
    fi
    # Restart missing API or frontend; never kill healthy processes.
    if ! curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:8505/api/overview || ! curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:8506/; then
      echo "[$(date -Is)] Service unhealthy; checking startup" >> "$LOG/autostart.log"
      bash scripts/start_bi_factory_codespaces.sh >> "$LOG/autostart.log" 2>&1 || echo "[$(date -Is)] Startup failed; retrying in 20s" >> "$LOG/autostart.log"
    fi
  fi
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    if ! pgrep -f '[p]ython3.*scripts/bi_factory_github_agent.py' >/dev/null; then
      setsid -f python3 -u scripts/bi_factory_github_agent.py >> "$LOG/github-agent.log" 2>&1 < /dev/null
      echo "[$(date -Is)] GitHub agent started" >> "$LOG/autostart.log"
    fi
  else
    echo "[$(date -Is)] GitHub CLI unauthenticated; agent unavailable" >> "$LOG/autostart.log"
  fi
  sleep 20
done
