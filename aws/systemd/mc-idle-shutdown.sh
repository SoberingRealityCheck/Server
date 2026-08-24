#!/usr/bin/env bash
# Power the instance off once the Minecraft container has stopped.
#
# The container stops itself when empty (ENABLE_AUTOSTOP). That frees
# CPU but saves no money: EC2 bills for a running instance regardless of
# what it is running. This script is the part that actually stops the
# meter.
#
# Run every minute by mc-idle-shutdown.timer.
#
# Three guards, because an over-eager shutdown is far more annoying than
# a few extra minutes of billing:
#
#   1. Boot grace  -- the container takes minutes to come up, and a
#                     freshly booted host has no container running yet.
#                     Shutting down during that window would make the
#                     instance un-wakeable: it would power off before a
#                     player could ever connect.
#   2. SSH sessions -- never yank the machine out from under someone
#                     doing maintenance.
#   3. Inhibit file -- an explicit override for long jobs like Chunky
#                     pre-generation, which runs for hours with no
#                     players connected and would otherwise look idle.

set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/home/ubuntu/Server}"
SERVICE="${SERVICE:-minecraft}"
BOOT_GRACE_SECONDS="${BOOT_GRACE_SECONDS:-900}"
INHIBIT_FILE="${INHIBIT_FILE:-/etc/mc-no-shutdown}"

log() { printf '%s mc-idle-shutdown: %s\n' "$(date -Is)" "$*"; }

# --- guard 1: boot grace ---------------------------------------------
# /proc/uptime's first field is seconds since boot, as a float.
uptime_seconds=$(cut -d. -f1 /proc/uptime)
if [ "$uptime_seconds" -lt "$BOOT_GRACE_SECONDS" ]; then
  log "up ${uptime_seconds}s, under ${BOOT_GRACE_SECONDS}s grace -- skipping"
  exit 0
fi

# --- guard 2: explicit inhibit ---------------------------------------
if [ -e "$INHIBIT_FILE" ]; then
  log "$INHIBIT_FILE present -- skipping"
  exit 0
fi

# `.skip-stop` suspends the container's own autostop; honour it here too
# so the two mechanisms cannot disagree.
if [ -e "$COMPOSE_DIR/data/.skip-stop" ]; then
  log "data/.skip-stop present -- skipping"
  exit 0
fi

# --- guard 3: someone is logged in ------------------------------------
if who | grep -q .; then
  log "active login session -- skipping"
  exit 0
fi

# --- is the server actually gone? -------------------------------------
# `ps --status running` lists only running containers for the service,
# so empty output means it has exited (auto-stopped) or never started.
running=$(cd "$COMPOSE_DIR" && docker compose ps --status running \
            --format '{{.Name}}' "$SERVICE" 2>/dev/null || true)

if [ -n "$running" ]; then
  exit 0
fi

log "container not running and no reason to stay up -- powering off"

# A shutdown may already be scheduled from a previous run of this
# script. Do not reschedule it -- the timer runs every minute, close to
# the delay below, so a repeat call can keep pushing the shutdown back
# and the instance never powers off.
if pgrep -x shutdown >/dev/null; then
  log "shutdown already scheduled -- not rescheduling"
  exit 0
fi

# Record why the container stopped, so the next person to look does not
# have to guess. Exit code 0 means a clean auto-stop; anything else
# means a crash. Written to /data so it survives the power-off.
exit_code=$(cd "$COMPOSE_DIR" && docker compose ps -a --format '{{.ExitCode}}' \
              "$SERVICE" 2>/dev/null | tail -n1 || true)
if [ -z "$exit_code" ]; then
  reason="never started"
elif [ "$exit_code" = "0" ]; then
  reason="auto-stop, no players"
else
  reason="crashed, exit code $exit_code"
fi
log "stop reason: $reason"
printf '%s %s\n' "$(date -Is)" "$reason" \
  > "$COMPOSE_DIR/data/.last-stop-reason" 2>/dev/null || true

# `+1` rather than `now`: gives systemd a moment to flush this log line,
# and leaves a one-minute window to cancel with `shutdown -c`.
/sbin/shutdown -h +1 "Minecraft server idle; stopping instance to save cost"
