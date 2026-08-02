#!/bin/ash
# Pterodactyl egg install script -- NOT run locally or over SFTP.
#
# Paste this into the egg's Install Script field: Panel Admin ->
# Nests -> (nest) -> Eggs -> (egg) -> Configuration -> Install Script.
# Base image for that field: ghcr.io/pterodactyl/installers:alpine
#
# Wings runs this in a throwaway container with the server's own volume
# mounted at /mnt/server whenever the server is (re)installed -- before
# it ever boots. No SFTP, no credentials, no external machine involved.
# Re-running a server's install (Panel -> server -> Settings -> Reinstall)
# re-fetches and re-applies datapacks from the pinned manifest.

set -e

apk add --no-cache curl yq coreutils

MANIFEST_URL="https://raw.githubusercontent.com/<github-user>/<repo>/main/minecraft/datapacks/datapacks.yaml"

mkdir -p /mnt/server/world/datapacks
cd /tmp
curl -fsSL "$MANIFEST_URL" -o datapacks.yaml

count=$(yq '.datapacks | length' datapacks.yaml)

i=0
while [ "$i" -lt "$count" ]; do
  name=$(yq -r ".datapacks[$i].name" datapacks.yaml)
  file=$(yq -r ".datapacks[$i].file" datapacks.yaml)
  url=$(yq -r ".datapacks[$i].url" datapacks.yaml)
  expected_sha512=$(yq -r ".datapacks[$i].sha512" datapacks.yaml)

  echo "==> $name"
  curl -fsSL "$url" -o "$file"

  actual_sha512=$(sha512sum "$file" | awk '{print $1}')
  if [ "$actual_sha512" != "$expected_sha512" ]; then
    echo "checksum mismatch for $file -- aborting" >&2
    exit 1
  fi

  cp "$file" /mnt/server/world/datapacks/
  echo "    installed"
  i=$((i + 1))
done

echo "Datapacks installed -- will be picked up when the world generates on first boot."
