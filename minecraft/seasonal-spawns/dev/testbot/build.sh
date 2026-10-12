#!/usr/bin/env bash
# Build the dev-only test bot into dev/testbot/testbot.jar. NOT part of the pack.
# Needs ../../build.sh to have run once, because it reuses the jars that script downloaded
# into ../../.build. Needs Java 25:  JAVA_HOME=/path/to/jdk-25 ./build.sh
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
build="$here/../../.build"
if [ -n "${JAVA_HOME:-}" ]; then PATH="$JAVA_HOME/bin:$PATH"; fi
[ -d "$build/mc" ] || { echo "Run ../../build.sh once first. It downloads what this needs." >&2; exit 1; }

cp_list="$build/loader.jar:$build/mixin.jar:$build/mc/META-INF/versions/26.2/server-26.2.jar"
for j in $(find "$build/fapi" "$build/mc/META-INF/libraries" -name '*.jar'); do
  cp_list="$cp_list:$j"
done

rm -rf "$here/.classes" && mkdir -p "$here/.classes"
javac --release 25 -proc:none -Xlint:-classfile -d "$here/.classes" -cp "$cp_list" \
  $(find "$here/src" -name '*.java')
cp "$here"/res/* "$here/.classes/"
(cd "$here/.classes" && jar cf "$here/testbot.jar" .)
echo "wrote $here/testbot.jar"
