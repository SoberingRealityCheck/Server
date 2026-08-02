#!/usr/bin/env bash
set -euo pipefail

# Reads datapacks.yaml, downloads each file, verifies it against the
# pinned sha512, and pushes it into a Wings-managed server's
# world/datapacks/ directory over SFTP.
#
# Requires: yq (https://github.com/mikefarah/yq) -- brew install yq
#           curl, sftp, sha512sum (all standard on Ubuntu; on macOS use
#           `shasum -a 512` instead if running this locally)
#
# The server has to already exist in the Panel before this is useful --
# SFTP access is per-server, not per-node. Get the connection details from
# the Panel: open the server, go to the file manager, and the SFTP
# username shown there is what WINGS_SFTP_USER needs.
#
# Usage:
#   WINGS_SFTP_HOST=mc-server \
#   WINGS_SFTP_USER='yourpanelusername.<8-char-server-id>' \
#   ./install.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$SCRIPT_DIR/datapacks.yaml"
CACHE_DIR="$SCRIPT_DIR/.cache"
mkdir -p "$CACHE_DIR"

: "${WINGS_SFTP_HOST:?set WINGS_SFTP_HOST, e.g. the mc-server SSH alias}"
: "${WINGS_SFTP_PORT:=2022}"
: "${WINGS_SFTP_USER:?set WINGS_SFTP_USER -- panelusername.serverid, from the Panel's file manager page}"

if ! command -v yq >/dev/null 2>&1; then
  echo "yq is required (brew install yq) -- aborting" >&2
  exit 1
fi

mc_version=$(yq -r '.minecraft_version' "$MANIFEST")
echo "Manifest targets Minecraft $mc_version"

count=$(yq '.datapacks | length' "$MANIFEST")

for i in $(seq 0 $((count - 1))); do
  name=$(yq -r ".datapacks[$i].name" "$MANIFEST")
  file=$(yq -r ".datapacks[$i].file" "$MANIFEST")
  url=$(yq -r ".datapacks[$i].url" "$MANIFEST")
  expected_sha512=$(yq -r ".datapacks[$i].sha512" "$MANIFEST")
  dest="$CACHE_DIR/$file"

  echo "==> $name"

  if [[ -f "$dest" ]] && echo "$expected_sha512  $dest" | sha512sum -c - >/dev/null 2>&1; then
    echo "    already downloaded and verified, skipping fetch"
  else
    echo "    downloading..."
    curl -fsSL "$url" -o "$dest"
    echo "$expected_sha512  $dest" | sha512sum -c -
    echo "    checksum OK"
  fi

  echo "    uploading to world/datapacks/ over SFTP..."
  sftp -P "$WINGS_SFTP_PORT" "$WINGS_SFTP_USER@$WINGS_SFTP_HOST" <<EOF
cd world/datapacks
put $dest
EOF

  echo "    done"
done

echo ""
echo "All datapacks installed. Run '/reload' in the server console (or"
echo "restart the server) for them to take effect -- datapacks are only"
echo "picked up on world load or an explicit reload, not automatically."
