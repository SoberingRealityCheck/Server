#!/usr/bin/env python3
"""Check the seasons tags against a LIVE local server.

Run from the repo root with `docker compose up -d` already running:

    python3 minecraft/tools/verify_seasons_live.py

For every Terralith biome it sets the biome at 0,80,0 with /fillbiome,
then asks each tag whether it matches, using `fillbiome ... replace
#tag`, which only changes biomes already in the tag. Then it compares
with the lists in seasons_terralith.py.

Why not `execute if biome`? It did not see the /fillbiome change in
testing, and always said the tag matched. The replace trick works.

Side effect: one biome cell at 0,80,0 in the world is overwritten.
It takes a few minutes, since it makes about 400 rcon calls.
"""
import sys,subprocess,zipfile,json,re,glob,time
sys.path.insert(0,"minecraft/tools")  # run from the repo root
import seasons_terralith as S
z=zipfile.ZipFile(glob.glob("data/mods/Terralith*.jar")[0])
biomes=sorted("terralith:"+m.group(1) for f in z.namelist() if (m:=re.match(r"data/terralith/worldgen/biome/(.+)\.json$",f)))
expect={"tropical_biomes":set(S.TROPICAL),"blacklisted_biomes":S.resolve(z,S.BLACKLISTED),"lesser_color_change_biomes":set(S.LESSER_COLOR)}
def r(c): return subprocess.run(["docker","compose","exec","-T","minecraft","rcon-cli",c],capture_output=True,text=True,timeout=60).stdout.strip()
def member(b,tag):
    o=r(f"fillbiome 0 80 0 0 80 0 {b} replace #sereneseasons:{tag}")
    return o.startswith("1 ")
r("forceload add 0 0"); time.sleep(2)
bad=0; n=0
for b in biomes:
    r(f"fillbiome 0 80 0 0 80 0 {b}")
    for tag,exp in expect.items():
        got=member(b,tag); n+=1
        if got!=(b in exp): bad+=1; print(f"MISMATCH {b} {tag}: live={got} expected={b in exp}")
print(f"\n{len(biomes)} Terralith biomes x 3 tags = {n} checks, {bad} mismatches")
print("vanilla entries still present (tags merged, not replaced):")
for b,tag,want in [("minecraft:desert","tropical_biomes",True),("minecraft:jungle","tropical_biomes",True),("minecraft:river","blacklisted_biomes",True),("minecraft:deep_dark","blacklisted_biomes",True),("minecraft:swamp","lesser_color_change_biomes",True),("minecraft:plains","tropical_biomes",False),("minecraft:plains","blacklisted_biomes",False)]:
    r(f"fillbiome 0 80 0 0 80 0 {b}")
    got=member(b,tag); print(f"  {b:20} {tag:28} live={got} expected={want} {'ok' if got==want else 'WRONG'}")
r("forceload remove 0 0")
