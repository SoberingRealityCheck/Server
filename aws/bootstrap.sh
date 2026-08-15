#!/usr/bin/env bash
# Provision a fresh Ubuntu 24.04 EC2 host to run this server.
#
# Installs Docker Engine + the Compose plugin and uv, clones this repo,
# builds the modpack, and starts the stack.
#
# Usage, as the `ubuntu` user on a fresh instance:
#
#   curl -fsSL <raw-url-to-this-file> -o bootstrap.sh
#   bash bootstrap.sh https://github.com/<user>/<repo>.git
#
# Or, if the repo is already cloned, run it from inside the clone with no
# arguments and it will skip the clone step.
#
# Safe to re-run: every step checks whether it already applies. That
# matters more than elegance here -- a half-finished bootstrap over a bad
# SSH connection should be fixable by running it again, not by rebuilding
# the instance.
#
# What this does NOT do: configure the security group, DNS, or Elastic
# IP. Those live in the AWS and DNS consoles -- see NOTES.md.

set -euo pipefail

REPO_URL="${1:-}"
CLONE_DIR="${CLONE_DIR:-$HOME/Server}"

# `id -un` rather than $USER: under `set -u`, $USER is unset in
# non-login shells -- which is exactly how this script runs when piped
# from curl or invoked by cloud-init.
RUN_USER="$(id -un)"

log()  { printf '\n\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- preflight -------------------------------------------------------

[ "$(id -u)" -eq 0 ] && die "run as a normal user (e.g. ubuntu), not root -- \
this script uses sudo where it needs to, and the repo should not end up \
owned by root."

command -v apt-get >/dev/null || die "expected a Debian/Ubuntu host"

total_mb=$(free -m | awk '/^Mem:/{print $2}')
if [ "$total_mb" -lt 7000 ]; then
  warn "this host has ${total_mb} MB RAM. The modpack wants 8 GB (t3.large)."
  warn "It will run, but set MC_MEMORY no higher than 3G in .env."
fi

# --- Docker ----------------------------------------------------------

if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  log "Docker and the Compose plugin are already installed"
else
  log "Installing Docker Engine and the Compose plugin"
  # Docker's own apt repo rather than Ubuntu's `docker.io` package: the
  # distro package ships docker-compose v1 (Python, unmaintained), and
  # this repo's compose file assumes the v2 plugin syntax.
  sudo apt-get update -qq
  sudo apt-get install -y -qq ca-certificates curl gnupg

  sudo install -m 0755 -d /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/docker.asc ]; then
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
      -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
  fi

  echo "deb [arch=$(dpkg --print-architecture) \
signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update -qq
  sudo apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi

# Run docker without sudo. The group change only takes effect in a new
# login session, so this script keeps using sudo for the rest of its run
# rather than pretending otherwise.
if ! id -nG "$RUN_USER" | grep -qw docker; then
  log "Adding $RUN_USER to the docker group"
  sudo usermod -aG docker "$RUN_USER"
  NEEDS_RELOGIN=1
fi

sudo systemctl enable --now docker

# --- uv --------------------------------------------------------------

if command -v uv >/dev/null; then
  log "uv is already installed"
else
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
# The installer writes to ~/.local/bin, which is not on PATH in a
# non-interactive shell.
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || die "uv installed but not on PATH"

# --- repo ------------------------------------------------------------

if [ -f "./docker-compose.yml" ] && [ -d "./minecraft" ]; then
  log "Already inside the repo, skipping clone"
  CLONE_DIR="$PWD"
elif [ -d "$CLONE_DIR/.git" ]; then
  log "Repo already at $CLONE_DIR, pulling"
  git -C "$CLONE_DIR" pull --ff-only
else
  [ -n "$REPO_URL" ] || die "pass the repo URL as the first argument, \
or run this from inside an existing clone"
  log "Cloning into $CLONE_DIR"
  sudo apt-get install -y -qq git
  git clone "$REPO_URL" "$CLONE_DIR"
fi

cd "$CLONE_DIR"

# --- config ----------------------------------------------------------

if [ -f .env ]; then
  log ".env already exists, leaving it alone"
else
  log "Creating .env from .env.example"
  cp .env.example .env
  if [ "$total_mb" -ge 7000 ]; then
    sed -i 's/^MC_MEMORY=.*/MC_MEMORY=6G/' .env
    log "Set MC_MEMORY=6G for this instance size"
  fi
  warn "Edit .env before players join -- MC_OPS and MC_WHITELIST are empty,"
  warn "and the whitelist is ON by default, so nobody can join yet."
fi

# --- build -----------------------------------------------------------

log "Building the modpack"
( cd minecraft && uv run --script build.py )

# --- start -----------------------------------------------------------

log "Starting the server"
sudo docker compose up -d

log "Done."
cat <<EOF

  The server is starting. First boot generates the world, which takes
  several minutes with this modpack -- it is not hung.

  Watch it:      sudo docker compose logs -f minecraft
  Check status:  sudo docker compose ps
  Console:       sudo docker compose exec minecraft rcon-cli

  The healthcheck reports "healthy" only once the server answers status
  pings, so 'ps' is the honest answer to "is it up yet".

EOF

if [ "${NEEDS_RELOGIN:-0}" = "1" ]; then
  cat <<EOF
  You were added to the docker group, which does not apply to this
  session. Log out and back in, after which you can drop the sudo:

    docker compose ps

EOF
fi

if grep -q '^MC_OPS=$' .env 2>/dev/null; then
  cat <<EOF
  Reminder: .env still has no operators or whitelisted players. Set
  MC_OPS and MC_WHITELIST, then:

    sudo docker compose up -d --force-recreate minecraft

EOF
fi
