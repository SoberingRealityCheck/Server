#!/usr/bin/env bash
# Compile the patch into ../../overrides/mods/elysium-dh-emissive.jar.
# Plain javac. No gradle. Needs: java 21+, curl. Not run by build.py.
# Set DH_JAR to use a local DH jar instead of downloading 3.3.2.
# The built jar is checked in. Rebuild only after editing src/.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="$here/.build"
mkdir -p "$work/classes"

M=https://maven.fabricmc.net
get() { [ -f "$work/$2" ] || curl -sfL -o "$work/$2" "$1"; }
get "$M/net/fabricmc/fabric-loader/0.19.5/fabric-loader-0.19.5.jar" loader.jar
get "$M/net/fabricmc/sponge-mixin/0.17.4%2Bmixin.0.8.7/sponge-mixin-0.17.4%2Bmixin.0.8.7.jar" mixin.jar
get "https://repo1.maven.org/maven2/io/github/llamalad7/mixinextras-common/0.5.5/mixinextras-common-0.5.5.jar" mixinextras.jar
DH_URL="https://cdn.modrinth.com/data/uCdwusMi/versions/9NoftEde/DistantHorizons-3.3.2-26.2-fabric-neoforge.jar"
if [ -n "${DH_JAR:-}" ]; then cp "$DH_JAR" "$work/dh.jar"; else get "$DH_URL" dh.jar; fi

rm -rf "$work/classes"
mkdir -p "$work/classes"
javac --release 21 -proc:none -d "$work/classes" \
  -cp "$work/loader.jar:$work/mixin.jar:$work/mixinextras.jar:$work/dh.jar" \
  $(find "$here/src" -name '*.java')
cp "$here"/res/* "$work/classes/"

out="$here/../../overrides/mods/elysium-dh-emissive.jar"
(cd "$work/classes" && jar cf "$out" .)
echo "wrote $out"
echo
java -cp "$work/classes" elysium.dhemissive.EmissiveFalloff
