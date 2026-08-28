#!/usr/bin/env bash
# Push the whitelist to the front-door proxy.
#
# The proxy (lazymc) refuses to wake this instance for a client that is
# not whitelisted, so login spam cannot run up an EC2 bill. lazymc
# cannot read this host's data/ directory, so a copy of the relevant
# files has to be sent to it. This is that copy.
#
# Triggered by mc-whitelist-sync.path whenever data/whitelist.json or
# data/ops.json changes -- which is every container start, since
# itzg/minecraft-server rewrites whitelist.json from MC_WHITELIST then.
# Also runnable by hand any time.
#
# Sends a 3-file tar over SSH to a key whose authorized_keys entry on
# the proxy forces `lazymc-recv-whitelist` and nothing else.

set -euo pipefail

DATA_DIR="${DATA_DIR:-/home/ubuntu/Server/data}"
SYNC_KEY="${SYNC_KEY:-/home/ubuntu/.ssh/mc-whitelist-sync}"
TARGET_FILE="${TARGET_FILE:-/etc/mc-whitelist-sync.target}"

log() { printf '%s mc-whitelist-sync: %s\n' "$(date -Is)" "$*"; }

# --- where to send it ------------------------------------------------
# First non-comment, non-blank line. e.g. ubuntu@10.0.1.23
target="$(sed -e 's/#.*//' -e 's/[[:space:]]//g' "$TARGET_FILE" 2>/dev/null \
            | grep -m1 . || true)"
if [ -z "$target" ]; then
  log "$TARGET_FILE not set to a host yet (ubuntu@<proxy-private-ip>). Skipping."
  exit 0
fi

[ -f "$SYNC_KEY" ] || { log "no sync key at $SYNC_KEY -- run bootstrap.sh. Skipping."; exit 0; }

# --- build the payload ---------------------------------------------------
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# whitelist.json and ops.json as itzg wrote them. Default either to an
# empty array if absent, so a later "whitelist off -> on" flip on this
# host can never leave the proxy holding a stale allow-all list.
for f in whitelist.json ops.json; do
  if [ -f "$DATA_DIR/$f" ]; then
    cp "$DATA_DIR/$f" "$work/$f"
  else
    printf '[]\n' > "$work/$f"
  fi
done

# Mirror this host's own white-list flag. If the game host runs open
# (MC_ENABLE_WHITELIST=false), the proxy must not be stricter -- lazymc
# reads `white-list` from this file and only enforces when it is true.
enabled="$(sed -n 's/^white-list=//p' "$DATA_DIR/server.properties" 2>/dev/null \
             | tr -d '[:space:]')"
printf 'white-list=%s\n' "${enabled:-true}" > "$work/server.properties"

# --- send it -----------------------------------------------------------
if tar -C "$work" -c whitelist.json ops.json server.properties \
     | ssh -T -i "$SYNC_KEY" \
           -o BatchMode=yes \
           -o StrictHostKeyChecking=accept-new \
           -o ConnectTimeout=10 \
           "$target"
then
  log "pushed whitelist (white-list=${enabled:-true}) to $target"
else
  log "push to $target failed"
  exit 1
fi
