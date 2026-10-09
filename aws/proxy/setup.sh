#!/usr/bin/env bash
# Provision the front-door proxy instance -- the small, always-on box
# that answers the public address, keeps the server visible while it is
# off, and wakes the game host on the first join.
#
# This is NOT bootstrap.sh. That script provisions the game host: it
# installs Docker and builds the modpack, neither of which belongs here.
# This box runs one thing, lazymc, and calls the EC2 API to start the
# other instance.
#
# Usage, as the `ubuntu` user on a fresh Ubuntu 24.04 instance, from
# inside a clone of this repo:
#
#   git clone https://github.com/SoberingRealityCheck/Server.git
#   cd Server
#   bash aws/proxy/setup.sh
#
# Safe to re-run: every step checks whether it already applies.
#
# What this does NOT do: create the instance, its security group, its
# Elastic IP, or the IAM instance profile; fill the placeholders in
# lazymc.toml; or point DNS at this box. See aws/NOTES.md,
# "Front door (auto-wake proxy)".

set -euo pipefail

LAZYMC_VERSION="0.2.11"
# Static build: no glibc version to match against a minimal AMI.
LAZYMC_ASSET="lazymc-v${LAZYMC_VERSION}-linux-x64-static"
LAZYMC_URL="https://github.com/timvisee/lazymc/releases/download/v${LAZYMC_VERSION}/${LAZYMC_ASSET}"

# Upstream publishes no checksums for its release assets. Run this script
# once, take the sha256 it prints for the downloaded binary, paste it
# here, and commit -- every later run then verifies against it and aborts
# on a mismatch. Left empty, the download is only version-pinned by URL.
LAZYMC_SHA256=""

CONFIG_DIR="/etc/lazymc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- preflight -----------------------------------------------------------

[ "$(id -u)" -eq 0 ] && die "run as a normal user (e.g. ubuntu), not root -- \
this script uses sudo where it needs to."

command -v apt-get >/dev/null || die "expected a Debian/Ubuntu host"

[ -f "$SCRIPT_DIR/lazymc.toml" ] || die "run this from inside the repo clone \
(expected $SCRIPT_DIR/lazymc.toml)"

# curl fetches the binaries; unzip unpacks the AWS CLI bundle.
if ! command -v curl >/dev/null || ! command -v unzip >/dev/null; then
  log "Installing curl and unzip"
  sudo apt-get update -qq
  sudo apt-get install -y -qq curl unzip
fi

# --- AWS CLI v2 --------------------------------------------------------

# Ubuntu's `awscli` package is the unmaintained v1. Install v2 from AWS's
# own bundle, matching the host architecture.
if command -v aws >/dev/null && aws --version 2>&1 | grep -q 'aws-cli/2'; then
  log "AWS CLI v2 already installed"
else
  log "Installing AWS CLI v2"
  case "$(uname -m)" in
    x86_64)  awscli_arch="x86_64" ;;
    aarch64) awscli_arch="aarch64" ;;
    *)       die "unsupported architecture $(uname -m) for the AWS CLI bundle" ;;
  esac
  tmp="$(mktemp -d)"
  curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${awscli_arch}.zip" \
    -o "$tmp/awscliv2.zip"
  unzip -q "$tmp/awscliv2.zip" -d "$tmp"
  sudo "$tmp/aws/install" --update
  rm -rf "$tmp"
fi

# --- lazymc ----------------------------------------------------------

installed_version=""
if command -v lazymc >/dev/null; then
  installed_version="$(lazymc --version 2>/dev/null | awk '{print $2}')"
fi

if [ "$installed_version" = "$LAZYMC_VERSION" ]; then
  log "lazymc $LAZYMC_VERSION already installed"
else
  log "Installing lazymc $LAZYMC_VERSION"
  tmp="$(mktemp -d)"
  curl -fsSL "$LAZYMC_URL" -o "$tmp/lazymc"
  got="$(sha256sum "$tmp/lazymc" | awk '{print $1}')"
  if [ -n "$LAZYMC_SHA256" ]; then
    [ "$got" = "$LAZYMC_SHA256" ] || die "sha256 mismatch for $LAZYMC_ASSET
  expected $LAZYMC_SHA256
  got      $got"
    log "sha256 verified: $got"
  else
    warn "no LAZYMC_SHA256 pinned. Downloaded $LAZYMC_ASSET has sha256:"
    warn "  $got"
    warn "paste that into LAZYMC_SHA256 near the top of this script and commit."
  fi
  sudo install -m 0755 "$tmp/lazymc" /usr/local/bin/lazymc
  rm -rf "$tmp"
fi

# --- config --------------------------------------------------------------

# ubuntu-owned: lazymc reads this dir as `ubuntu`, and the whitelist
# receiver (also `ubuntu`, via SSH forced command) writes into it.
sudo install -d -m 0755 -o ubuntu -g ubuntu "$CONFIG_DIR"

if [ -f "$CONFIG_DIR/lazymc.toml" ]; then
  log "$CONFIG_DIR/lazymc.toml already exists, leaving it alone"
else
  log "Installing lazymc.toml to $CONFIG_DIR"
  install -m 0644 "$SCRIPT_DIR/lazymc.toml" "$CONFIG_DIR/lazymc.toml"
  warn "Edit $CONFIG_DIR/lazymc.toml before starting the service:"
  warn "  - server.address : the game host's PRIVATE IP"
  warn "  - server.command : the game host's instance ID"
  warn "  (public.version / public.protocol are optional -- see the file)"
fi

# --- whitelist enforcement ---------------------------------------------
#
# lazymc only applies a whitelist when server.properties in this dir has
# `white-list=true`. The game host's whitelist.json / ops.json / this
# flag are pushed here by aws/systemd/mc-whitelist-sync.* whenever they
# change. Until the first push, seed an *empty* whitelist so the proxy
# fails closed -- no wake -- rather than open.

if [ ! -f "$CONFIG_DIR/server.properties" ]; then
  log "Seeding $CONFIG_DIR/server.properties (white-list=true)"
  printf 'white-list=true\n' > "$CONFIG_DIR/server.properties"
fi
if [ ! -f "$CONFIG_DIR/whitelist.json" ]; then
  log "Seeding an empty $CONFIG_DIR/whitelist.json (fails closed until first sync)"
  printf '[]\n' > "$CONFIG_DIR/whitelist.json"
fi

log "Installing the whitelist receiver"
sudo install -m 0755 "$SCRIPT_DIR/lazymc-recv-whitelist" /usr/local/bin/lazymc-recv-whitelist

# The game host authenticates with a dedicated key whose authorized_keys
# entry forces the receiver and nothing else. Create the file if absent
# so the operator only has to append one line.
sudo install -d -m 0700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
sudo touch /home/ubuntu/.ssh/authorized_keys
sudo chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
sudo chmod 600 /home/ubuntu/.ssh/authorized_keys

# --- systemd unit ------------------------------------------------------

log "Installing the systemd unit"
sudo install -m 0644 "$SCRIPT_DIR/lazymc.service" /etc/systemd/system/lazymc.service
sudo systemctl daemon-reload
sudo systemctl enable lazymc.service

# --- voice chat relay --------------------------------------------------

log "Installing the voice chat relay"
sudo apt-get install -y -qq socat
if [ ! -f "$CONFIG_DIR/voice.env" ]; then
  printf 'VOICE_TARGET=REPLACE_WITH_GAME_HOST_PRIVATE_IP\n' > "$CONFIG_DIR/voice.env"
  warn "Edit $CONFIG_DIR/voice.env: VOICE_TARGET is the game host's PRIVATE IP"
fi
sudo install -m 0644 "$SCRIPT_DIR/voice-forward.service" /etc/systemd/system/voice-forward.service
sudo systemctl daemon-reload
sudo systemctl enable voice-forward.service

# --- done ------------------------------------------------------------

log "Done."
cat <<EOF

  lazymc is installed but NOT started -- it needs these first:

  1. Fill the placeholders in $CONFIG_DIR/lazymc.toml (see warnings above).

  2. Attach an IAM instance profile to THIS instance whose policy is
     aws/proxy/iam-policy.json (account ID and game-host instance ID
     substituted). Verify from this box:

       aws ec2 describe-instances --region us-east-2 \\
         --instance-ids <game-host-id> --query 'Reservations[].Instances[].State.Name'

  3. Authorise the game host to push whitelist updates: append its sync
     public key to /home/ubuntu/.ssh/authorized_keys on THIS box, forced
     to the receiver:

       command="/usr/local/bin/lazymc-recv-whitelist",restrict ssh-ed25519 AAAA... game-host-whitelist-sync

     bootstrap.sh on the game host prints that key. Then, from the game
     host, run /usr/local/bin/mc-whitelist-sync.sh once to seed the real
     list (until then this box fails closed -- nobody can wake it).

  4. Check the filled config parses, then start it:

       lazymc config test --config /etc/lazymc/lazymc.toml
       sudo systemctl start lazymc
       journalctl -u lazymc -f

  5. Voice chat: set VOICE_TARGET in $CONFIG_DIR/voice.env to the game
     host's private IP, then:

       sudo systemctl start voice-forward

     Both security groups need UDP 24454 too. See aws/NOTES.md, section 3.

  Then point the mc.<domain> A record at THIS instance's Elastic IP and
  test a real join. See aws/NOTES.md, "Front door (auto-wake proxy)".

EOF
