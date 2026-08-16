#!/bin/sh
set -u

interval="${SYNC_INTERVAL_SECONDS:-3600}"
child_pid=""

term() {
  if [ -n "${child_pid}" ]; then
    kill "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
  exit 0
}

trap term TERM INT

while true; do
  python -m openhedge_core.sync_markets &
  child_pid=$!
  wait "${child_pid}" || echo "sync_markets exited with $?" >&2

  sleep "${interval}" &
  child_pid=$!
  wait "${child_pid}" || true
done
