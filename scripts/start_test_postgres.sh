#!/usr/bin/env bash
set -euo pipefail

PG_BIN="${TEST_POSTGRES_BIN:-/usr/lib/postgresql/16/bin}"
PG_DATA="${TEST_POSTGRES_DATA_DIR:-/tmp/bi_factory_postgres}"
PG_SOCKET="${TEST_POSTGRES_SOCKET_DIR:-/tmp}"
PG_PORT="${TEST_POSTGRES_PORT:-55432}"
PG_DB="${TEST_POSTGRES_DB:-bi_factory_test}"
PG_USER="${TEST_POSTGRES_USER:-$(id -un)}"

if [[ ! -x "$PG_BIN/initdb" || ! -x "$PG_BIN/pg_ctl" ]]; then
  echo "PostgreSQL server binaries not found in $PG_BIN" >&2
  exit 1
fi

if [[ ! -f "$PG_DATA/PG_VERSION" ]]; then
  mkdir -p "$PG_DATA"
  chmod 700 "$PG_DATA"
  "$PG_BIN/initdb" -D "$PG_DATA" --auth-local=trust --auth-host=trust --encoding=UTF8 --no-locale >/dev/null
fi

if ! "$PG_BIN/pg_ctl" -D "$PG_DATA" status >/dev/null 2>&1; then
  "$PG_BIN/pg_ctl" -D "$PG_DATA" -l "$PG_DATA/server.log" \
    -o "-h 127.0.0.1 -p $PG_PORT -k $PG_SOCKET" start -w >/dev/null
fi

if ! "$PG_BIN/psql" -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" -d postgres -Atqc \
  "SELECT 1 FROM pg_database WHERE datname = '$PG_DB'" | grep -q 1; then
  "$PG_BIN/createdb" -h 127.0.0.1 -p "$PG_PORT" -U "$PG_USER" "$PG_DB"
fi

echo "TEST_POSTGRES_HOST=127.0.0.1"
echo "TEST_POSTGRES_PORT=$PG_PORT"
echo "TEST_POSTGRES_DB=$PG_DB"
echo "TEST_POSTGRES_USER=$PG_USER"
