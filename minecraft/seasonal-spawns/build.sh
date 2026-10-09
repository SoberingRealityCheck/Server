#!/usr/bin/env bash
# Compile the mod into ../server-overrides/mods/elysium-seasonal-spawns.jar,
# run the self-test, then print the rule table.
# Plain javac. No gradle. Not run by build.py. The built jar is checked in.
#
# Needs: Java 25 (the game jar is class version 69), curl, unzip.
#   JAVA_HOME=/path/to/jdk-25 ./build.sh
# Everything it downloads lands in .build/ (ignored by git).
#
# Pass "test" to skip the jar and only run the self-test + table. That
# is the fast loop when you are editing .rules files.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
work="$here/.build"
rules_dir="$here/../server-overrides/config/elysium-seasonal-spawns"
out="$here/../server-overrides/mods/elysium-seasonal-spawns.jar"

if [ -n "${JAVA_HOME:-}" ]; then PATH="$JAVA_HOME/bin:$PATH"; fi
major="$(javac -version 2>&1 | sed -E 's/javac ([0-9]+).*/\1/')"
if [ "$major" -lt 25 ]; then
  echo "javac is $major. Need 25. Set JAVA_HOME to a JDK 25 and run again." >&2
  exit 1
fi
mkdir -p "$work"

# --- downloads (all pinned, all from the same sources pack.yaml uses) ----
get() { [ -f "$work/$2" ] || curl -sfL -o "$work/$2" "$1"; }
M=https://maven.fabricmc.net
get "$M/net/fabricmc/fabric-loader/0.19.5/fabric-loader-0.19.5.jar" loader.jar
get "$M/net/fabricmc/sponge-mixin/0.17.4%2Bmixin.0.8.7/sponge-mixin-0.17.4%2Bmixin.0.8.7.jar" mixin.jar
get "https://piston-data.mojang.com/v1/objects/823e2250d24b3ddac457a60c92a6a941943fcd6a/server.jar" mc-bundle.jar
get "https://cdn.modrinth.com/data/P7dR8mSH/versions/ewUK83HI/fabric-api-0.161.0%2B26.2.jar" fabric-api.jar
get "https://cdn.modrinth.com/data/e0bNACJD/versions/q5mzi8wy/SereneSeasons-fabric-26.2-26.1.2.0.6.jar" serene.jar

# --- unpack what javac needs ---------------------------------------------
if [ ! -d "$work/mc" ]; then
  unzip -qo "$work/mc-bundle.jar" 'META-INF/versions/26.2/server-26.2.jar' 'META-INF/libraries/*' -d "$work/mc"
fi
if [ ! -d "$work/fapi" ]; then
  mkdir -p "$work/fapi"
  for part in fabric-api-base fabric-command-api-v2 fabric-lifecycle-events-v1; do
    unzip -qo "$work/fabric-api.jar" "META-INF/jars/$part-*.jar" -d "$work/fapi"
  done
fi

cp_list="$work/loader.jar:$work/mixin.jar:$work/serene.jar:$work/mc/META-INF/versions/26.2/server-26.2.jar"
for j in $(find "$work/fapi" "$work/mc/META-INF/libraries" -name '*.jar'); do
  cp_list="$cp_list:$j"
done

# --- compile -------------------------------------------------------------
rm -rf "$work/classes"
mkdir -p "$work/classes"
# -Xlint:-classfile hides noise about annotation jars the game does not ship.
javac --release 25 -proc:none -Xlint:-classfile -d "$work/classes" -cp "$cp_list" \
  $(find "$here/src" -name '*.java')
cp "$here"/res/* "$work/classes/"

# --- check ---------------------------------------------------------------
echo "== self-test"
java -cp "$work/classes" elysium.seasonalspawns.SelfTest
echo
echo "== rule table"
java -cp "$work/classes" elysium.seasonalspawns.Table "$rules_dir"

if [ "${1:-}" = "test" ]; then exit 0; fi
mkdir -p "$(dirname "$out")"
(cd "$work/classes" && jar cf "$out" .)
echo
echo "wrote $out"
