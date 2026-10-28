#!/usr/bin/env bash
# Compile the mod into ../overrides/mods/elysium_flora.jar (both sides: it adds blocks).
# Plain javac, no gradle, same as elysium-atlas/build.sh. Not run by build.py. The built jar is checked in.
# 26.x jars are unobfuscated, so nothing needs remapping.
#
# Needs: Java 25 (the game jar is class version 69), curl, unzip, python3.
#   JAVA_HOME=/path/to/jdk-25 ./build.sh
# Everything it downloads lands in .build/ (ignored by git). Generated JSON comes from tools/gen_assets.py.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="$here/.build"
version=0.1.0
out="$here/../overrides/mods/elysium_flora.jar"

if [ -n "${JAVA_HOME:-}" ]; then PATH="$JAVA_HOME/bin:$PATH"; fi
major="$(javac -version 2>&1 | sed -nE 's/^javac ([0-9]+).*/\1/p')"
if [ "$major" -lt 25 ]; then
  echo "javac is $major. Need 25. Set JAVA_HOME to a JDK 25 and run again." >&2
  exit 1
fi
mkdir -p "$work"

# --- downloads (pinned, same sources as elysium-atlas) -------------------
get() { [ -f "$work/$2" ] || curl -sfL -o "$work/$2" "$1"; }
get "https://maven.fabricmc.net/net/fabricmc/fabric-loader/0.19.5/fabric-loader-0.19.5.jar" loader.jar
get "https://piston-data.mojang.com/v1/objects/823e2250d24b3ddac457a60c92a6a941943fcd6a/server.jar" mc-bundle.jar
get "https://cdn.modrinth.com/data/P7dR8mSH/versions/ewUK83HI/fabric-api-0.161.0%2B26.2.jar" fabric-api.jar

if [ ! -d "$work/mc" ]; then
  unzip -qo "$work/mc-bundle.jar" 'META-INF/versions/26.2/server-26.2.jar' 'META-INF/libraries/*' -d "$work/mc"
fi
if [ ! -d "$work/fapi" ]; then
  mkdir -p "$work/fapi"
  unzip -qo "$work/fabric-api.jar" 'META-INF/jars/*.jar' -d "$work/fapi"
fi
cp_list="$work/loader.jar:$work/mc/META-INF/versions/26.2/server-26.2.jar"
for j in $(find "$work/fapi" "$work/mc/META-INF/libraries" -name '*.jar'); do
  cp_list="$cp_list:$j"
done

# --- generate, compile, jar ----------------------------------------------
python3 "$here/tools/gen_assets.py"
rm -rf "$work/classes"
mkdir -p "$work/classes"
javac --release 25 -proc:none -Xlint:-classfile -d "$work/classes" -cp "$cp_list" \
  $(find "$here/src/main/java" -name '*.java')
cp -r "$here"/src/main/resources/. "$work/classes/"
sed -i.bak "s/\${version}/$version/" "$work/classes/fabric.mod.json" && rm "$work/classes/fabric.mod.json.bak"
cp "$here/LICENSE" "$work/classes/LICENSE_elysium_flora"

mkdir -p "$(dirname "$out")"
(cd "$work/classes" && jar cf "$out" .)
echo "wrote $out"
