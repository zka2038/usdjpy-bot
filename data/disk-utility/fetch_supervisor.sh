#!/bin/bash
# Auto-restart watcher for the spec 004 gap-fill fetch (scripts/download_gap_fill.py all).
#
#   bash fetch_supervisor.sh start     # copy to the internal disk and run there, detached
#   bash fetch_supervisor.sh status    # is it running?, last lines of its own log
#   bash fetch_supervisor.sh stop      # stop the watcher (the fetch keeps running)
#
# Why: the fetch dies without a trace when the external drive hiccups, is unplugged, or the
# Mac sleeps (handoffs/HANDOFF-2026-11-26-remaining.md §2). The handoff's rule is that the
# fetch is restarted, never abandoned; this does it within about a minute, unattended.
#
# What it does, every POLL seconds: if the drive is absent, wait for it. If fetch.log ends
# with "stage 3 complete", stop for good. If no fetch process is running, confirm after
# GRACE seconds, then start one exactly as the manual procedure does (from the main checkout,
# under caffeinate -i, appending to data/tokyo_hours/fetch.log after a dated
# "--- restarted ... by fetch_supervisor ---" line) and write the Python PID to fetch.pid.
# At most MAX_PER_HOUR restarts an hour; past that it backs off BACKOFF seconds.
#
# It never starts a second fetch while one runs, never sends a request itself, and reads
# nothing under data/tokyo_hours/ except fetch.log's tail (blinding: spec 004 Gap fill).
# It runs from the INTERNAL disk (STATE_DIR), so a drive dropout cannot kill it. It cannot
# stop the Mac sleeping on battery with the lid closed: keep the Mac on mains power.
#
# Committed copy: data/disk-utility/ in the repo. Running copy: $STATE_DIR (see below).
# Settings can be overridden by environment variables (the tests use this).
set -u

REPO="${REPO:-/Volumes/bzk Drive/usdjpy-bot}"
PY="${PY:-$HOME/.venvs/usdjpy-bot/bin/python}"
STATE_DIR="${STATE_DIR:-$HOME/usdjpy-fetch-supervisor}"
POLL="${POLL:-30}"
GRACE="${GRACE:-60}"
MAX_PER_HOUR="${MAX_PER_HOUR:-6}"
BACKOFF="${BACKOFF:-900}"
FETCH_ARGS="scripts/download_gap_fill.py all"
TREE="$REPO/data/tokyo_hours"
SLOG="$STATE_DIR/supervisor.log"
SPID="$STATE_DIR/supervisor.pid"

now() { date -u +"%Y-%m-%d %H:%M:%S"; }
say() { echo "$(now) UTC  $*" >> "$SLOG"; }
fetch_pids() { pgrep -f "$PY -u $FETCH_ARGS" || true; }
running_supervisor() { [ -f "$SPID" ] && kill -0 "$(cat "$SPID")" 2>/dev/null; }

fetch_python_pid() {
  # The fetch's own process, not the caffeinate wrapping it (whose command line also matches).
  local p c
  for p in $(fetch_pids); do
    c=$(ps -p "$p" -o command= 2>/dev/null)
    if [ -n "$c" ] && [ "${c#caffeinate}" = "$c" ]; then echo "$p"; return; fi
  done
}

start_fetch() {
  echo "--- restarted $(date -u +'%Y-%m-%d %H:%M') UTC by fetch_supervisor (no fetch process found) ---" >> "$TREE/fetch.log"
  ( cd "$REPO" && nohup caffeinate -i "$PY" -u $FETCH_ARGS >> "$TREE/fetch.log" 2>&1 < /dev/null & )
  sleep 5
  local pid
  pid=$(fetch_python_pid)
  if [ -n "$pid" ]; then echo "$pid" > "$TREE/fetch.pid"; say "fetch started, python pid $pid"; else say "fetch start FAILED (no python process after 5 s)"; fi
}

run() {
  mkdir -p "$STATE_DIR"
  cd "$STATE_DIR" || exit 1
  echo $$ > "$SPID"
  say "supervisor up (pid $$; repo $REPO; poll ${POLL}s, grace ${GRACE}s, max ${MAX_PER_HOUR}/h)"
  local restarts=() drive_gone=0
  while true; do
    if [ ! -d "$TREE" ]; then
      [ $drive_gone -eq 0 ] && say "drive absent ($TREE); waiting"
      drive_gone=1; sleep 15; continue
    fi
    [ $drive_gone -eq 1 ] && say "drive back"
    drive_gone=0
    if tail -n 5 "$TREE/fetch.log" 2>/dev/null | grep -q "stage 3 complete"; then
      say "fetch.log reports stage 3 complete; supervisor exits"; rm -f "$SPID"; exit 0
    fi
    if [ -n "$(fetch_pids)" ]; then sleep "$POLL"; continue; fi
    say "no fetch process; confirming in ${GRACE}s"
    sleep "$GRACE"
    [ -d "$TREE" ] || continue
    [ -n "$(fetch_pids)" ] && { say "fetch process present again; nothing to do"; continue; }
    local t; t=$(date +%s); local kept=()
    for r in "${restarts[@]+"${restarts[@]}"}"; do [ $((t - r)) -lt 3600 ] && kept+=("$r"); done
    restarts=("${kept[@]+"${kept[@]}"}")
    if [ "${#restarts[@]}" -ge "$MAX_PER_HOUR" ]; then
      say "${#restarts[@]} restarts in the last hour; backing off ${BACKOFF}s"; sleep "$BACKOFF"; continue
    fi
    start_fetch
    restarts+=("$t")
    sleep "$POLL"
  done
}

case "${1:-}" in
  run) run ;;
  start)
    mkdir -p "$STATE_DIR"
    if running_supervisor; then echo "already running (pid $(cat "$SPID")); log: $SLOG"; exit 0; fi
    src="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
    [ "$src" != "$STATE_DIR/fetch_supervisor.sh" ] && cp "$src" "$STATE_DIR/fetch_supervisor.sh"
    cd "$STATE_DIR" && nohup caffeinate -i /bin/bash "$STATE_DIR/fetch_supervisor.sh" run >> "$STATE_DIR/nohup.out" 2>&1 < /dev/null &
    sleep 2
    if running_supervisor; then echo "supervisor running (pid $(cat "$SPID")); log: $SLOG"; else echo "failed to start; see $STATE_DIR/nohup.out"; exit 1; fi ;;
  stop)
    if running_supervisor; then kill "$(cat "$SPID")" && rm -f "$SPID" && echo "supervisor stopped (the fetch keeps running)"; else echo "not running"; fi ;;
  status)
    if running_supervisor; then echo "supervisor RUNNING (pid $(cat "$SPID"))"; else echo "supervisor NOT running"; fi
    p=$(fetch_pids); [ -n "$p" ] && echo "fetch process(es): $(echo $p)" || echo "no fetch process"
    echo "--- $SLOG (last 10) ---"; tail -n 10 "$SLOG" 2>/dev/null ;;
  *) echo "usage: bash $0 start|status|stop|run"; exit 2 ;;
esac
