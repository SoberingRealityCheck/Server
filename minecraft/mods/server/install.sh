#!/bin/sh
# Pterodactyl egg install script for the Fabric "realistic terrain"
# profile's SERVER-side mods -- this is the deployed server's mod
# installer, NOT run locally. Paste into a Fabric egg's Install Script
# field (Panel Admin -> Nests -> Eggs -> Configuration), or curl+run it
# from within a combined install script (e.g. appended after the Fabric
# loader install step). No assumptions about the installer container's
# package manager -- works under Alpine or Debian-based images.
#
# Only installs mods that have a real server-side role (see mods.yaml's
# header comment for the reasoning per mod). Client-only mods live in
# ../client/ and are never touched by this script -- there's no mechanism
# for Pterodactyl to install anything on a player's own machine, so those
# are manual-install, documented only.
#
# Runs in a throwaway container with the server's volume mounted at
# /mnt/server, before the server ever boots. Fabric mods don't need
# explicit load order -- everything just needs to land in
# /mnt/server/mods/ and Fabric Loader resolves dependencies at startup.

set -e

command -v apk >/dev/null 2>&1 && apk add --no-cache curl coreutils
command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y curl coreutils
command -v yq >/dev/null 2>&1 || {
  curl -fsSL -o /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64"
  chmod +x /usr/local/bin/yq
}

MANIFEST_URL="https://raw.githubusercontent.com/<github-user>/<repo>/main/minecraft/mods/server/mods.yaml"

mkdir -p /mnt/server/mods
cd /tmp
curl -fsSL "$MANIFEST_URL" -o mods.yaml

count=$(yq '.mods | length' mods.yaml)

i=0
while [ "$i" -lt "$count" ]; do
  name=$(yq -r ".mods[$i].name" mods.yaml)
  file=$(yq -r ".mods[$i].file" mods.yaml)
  url=$(yq -r ".mods[$i].url" mods.yaml)
  expected_sha512=$(yq -r ".mods[$i].sha512" mods.yaml)

  echo "==> $name"
  curl -fsSL "$url" -o "$file"

  actual_sha512=$(sha512sum "$file" | awk '{print $1}')
  if [ "$actual_sha512" != "$expected_sha512" ]; then
    echo "checksum mismatch for $file -- aborting" >&2
    exit 1
  fi

  cp "$file" /mnt/server/mods/
  echo "    installed"
  i=$((i + 1))
done

echo "Server-side mods installed. Requires a Fabric egg targeting Minecraft 26.2."
echo "See ../client/MODLIST.md for mods players should add to their own client."
