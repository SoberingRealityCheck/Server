#!/bin/sh
# Build the mod and copy the jar into the pack's client-overrides.
# HACK: the jar is committed, so it can drift from the source. Run this
# after any change to the mod, then commit both. Goes away once the mod
# has a public release and pack.yaml pins its URL + sha512 instead.
set -e
cd "$(dirname "$0")"
./gradlew build
rm -f ../../client-overrides/mods/ssdh26-*.jar
cp build/libs/ssdh26-1.0.0.jar ../../client-overrides/mods/
ls -l ../../client-overrides/mods/
