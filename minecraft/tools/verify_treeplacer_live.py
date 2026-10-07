#!/usr/bin/env python3
"""Grow saplings on a LIVE local server and check what comes out.

Run from the repo root with the server up AND A PLAYER LOGGED IN (anywhere
in the world. The test grid is built around them):

    python3 -u minecraft/tools/verify_treeplacer_live.py [BIOMES_PER_SAPLING] [REPS] [--only=oak_sapling,...]

Why a player: with nobody online the server pauses (pause-when-empty-seconds,
default 60) and game time stops. No random tick ever runs, so nothing grows.
The script checks this first and stops with a message if time is frozen.

How it works. The WORLD is parallel and the RCON is not. Every case is planted at once, each 32 blocks from the next, inside the
chunks already loaded around the player. One burst of fast random ticks grows them all.
Then each cell is read and cleared, one after another. Never run RCON
commands in parallel: Minecraft collects every reply in one shared buffer, so
parallel clients read each other's answers. That made the first versions of
this script report the same leaf counts under different saplings.

  1. Clear a column of air high above the terrain and lay a grass platform.
  2. Set the biome at the sapling with /fillbiome. Treeplacer looks up
     the biome at the sapling, so this picks the mapping.
  3. Plant. One sapling, or four in a square for a 2x2 "mega" tree.
  4. Pin the season to mid spring and set random_tick_speed to 3000 for a
     few seconds.
  5. If the sapling block is gone, count log and leaf types with
     /fill ... replace. The command reports how many it replaced, which
     counts them and clears them in one step.

A mapped case passes if every log and leaf type it grew is one the mapped
trees can make. The server will not say WHICH tree grew, so this is a block
mix check, not a proof of the exact tree. Controls in vanilla biomes show
what vanilla growth looks like.

Side effects: edits blocks in a patch of sky and sets biome cells there.
Pins the season to mid spring. Resets random_tick_speed to 3 when done.
Use a test world.
"""
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BASE = ROOT / "minecraft/server-overrides/world/datapacks/z-treeplacer-terralith/data/treeplacer_terralith/sapling_overrides"
PER_SAPLING = int(sys.argv[1]) if len(sys.argv) > 1 else 3
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 1

# Layout. Cells sit on a grid CELL blocks apart, centred on wherever the
# player is, so every cell is inside the chunks the server already keeps
# loaded and ticking around them (view and simulation distance are 10
# chunks, so 160 blocks). No forceload needed, which also avoids the
# 256-chunk forceload limit. The grid is about 224 x 256 blocks plus R. R is how far we clear and read from the
# sapling. A tree wider than R is cut off in the read. That is fine for
# a block-mix check.
CELL, COLS = 32, 8
R, Y_FLOOR, Y_TOP = 15, 199, 231     # one slab, 31*31*33 blocks, under /fill's limit
SAPLING_Y = 201



def rcon(cmd):
    return subprocess.run(["docker", "compose", "exec", "-T", "minecraft", "rcon-cli", cmd],
                          capture_output=True, text=True, timeout=120, cwd=ROOT).stdout.strip()


def filled(cmd):
    m = re.search(r"filled (\d+)", rcon(cmd))
    return int(m.group(1)) if m else 0


# --- what a mapped tree can be made of --------------------------------

T = zipfile.ZipFile(next((ROOT / "data/mods").glob("Terralith*.jar")))
V = zipfile.ZipFile(ROOT / "data/versions/26.2/server-26.2.jar")


def feature_blocks(fid):
    ns, p = fid.split(":")
    name = f"data/{ns}/worldgen/configured_feature/{p}.json"
    for z in (T, V):
        try:
            c = json.loads(z.read(name))["config"]
            break
        except KeyError:
            pass

    def names(pr):
        if not pr:
            return set()
        t = pr["type"]
        if t in ("minecraft:simple_state_provider", "minecraft:rotated_block_provider"):
            return {pr["state"]["Name"]}
        if t == "minecraft:weighted_state_provider":
            return {e["data"]["Name"] for e in pr["entries"]}
        if t == "minecraft:randomized_int_state_provider":
            return names(pr["source"])
        return set()

    return names(c.get("trunk_provider")), names(c.get("foliage_provider"))


SPECIES = ["oak", "birch", "spruce", "jungle", "acacia", "dark_oak", "cherry", "mangrove", "pale_oak"]
LEAVES = [f"{x}_leaves" for x in SPECIES] + ["azalea_leaves", "flowering_azalea_leaves"]


def log_species(blocks):
    out = set()
    for b in blocks:
        m = re.match(r"minecraft:(?:stripped_)?(.+?)(?:_log|_wood)$", b)
        if m:
            out.add(m.group(1))
    return out


# --- the cases --------------------------------------------------------

ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)


def build_cases():
    cases = []
    for f in sorted(BASE.glob("*/minecraft/*.json")):
        kind, sap = f.parts[-3], f.stem
        if ONLY and sap not in ONLY:
            continue
        vals = json.loads(f.read_text())["values"]
        for biome in list(vals)[:PER_SAPLING]:
            feats = [e["feature"] for e in vals[biome]]
            trunks, leaves = set(), set()
            for x in feats:
                t, l = feature_blocks(x)
                trunks |= t
                leaves |= l
            cases.append({"label": "mapped", "sap": sap, "kind": kind, "biome": biome,
                          "logs": log_species(trunks), "leaves": {b.split(":")[1] for b in leaves}})
    # The three cases that looked odd in the first run, repeated more.
    odd = [("jungle_sapling", "single", "terralith:desert_oasis"),
           ("dark_oak_sapling", "single", "terralith:forested_highlands"),
           ("pale_oak_sapling", "single", "terralith:moonlight_grove")]
    for sap, kind, biome in odd:
        if ONLY and sap not in ONLY:
            continue
        vals = json.loads((BASE / kind / "minecraft" / f"{sap}.json").read_text())["values"]
        trunks, leaves = set(), set()
        for e in vals[biome]:
            t, l = feature_blocks(e["feature"])
            trunks |= t
            leaves |= l
        for _ in range(4):
            cases.append({"label": "odd", "sap": sap, "kind": kind, "biome": biome,
                          "logs": log_species(trunks), "leaves": {b.split(":")[1] for b in leaves}})
    # Controls in a vanilla biome. No mapping applies there.
    for sap, kind, grows in [("oak_sapling", "single", True), ("jungle_sapling", "single", True),
                             ("dark_oak_sapling", "single", False)]:
        for _ in range(2):
            cases.append({"label": "control", "sap": sap, "kind": kind, "biome": "minecraft:plains",
                          "logs": None, "leaves": None, "grows": grows})
    out = []
    for c in cases:
        reps = REPS if c["label"] == "mapped" else 1
        out += [dict(c) for _ in range(reps)]
    return out


def place_grid(cases):
    """Centre the grid on the player. Returns (x, z) of the player."""
    m = re.search(r"\[(-?[\d.]+)d, (-?[\d.]+)d, (-?[\d.]+)d\]", rcon("data get entity @p Pos"))
    if not m:
        return None
    px, pz = int(float(m.group(1))), int(float(m.group(3)))
    rows = (len(cases) + COLS - 1) // COLS
    x0 = px - (COLS - 1) * CELL // 2
    z0 = pz - (rows - 1) * CELL // 2
    for i, c in enumerate(cases):
        c["cx"] = x0 + (i % COLS) * CELL
        c["cz"] = z0 + (i // COLS) * CELL
    return px, pz


# --- phases -----------------------------------------------------------

def setup(c):
    cx, cz = c["cx"], c["cz"]
    rcon(f"fill {cx-R} {Y_FLOOR} {cz-R} {cx+R} {Y_TOP} {cz+R} minecraft:air")
    rcon(f"fill {cx-3} 200 {cz-3} {cx+3} 200 {cz+3} minecraft:grass_block")
    # Minecraft does not read the biome at a block exactly. It blends between
    # the surrounding 4x4x4 biome cells, picking one with a position-based
    # random offset. A patch of one or two cells leaves some positions
    # reading a neighbouring cell, which still holds the sky's original
    # biome. So set a block of cells wide enough that every neighbour of
    # the sapling's cell is the test biome too.
    rcon(f"fillbiome {cx-5} {SAPLING_Y-5} {cz-5} {cx+6} {SAPLING_Y+6} {cz+6} {c['biome']}")
    spots = [(0, 0)] if c["kind"] == "single" else [(0, 0), (1, 0), (0, 1), (1, 1)]
    out = [rcon(f"setblock {cx+dx} {SAPLING_Y} {cz+dz} minecraft:{c['sap']}") for dx, dz in spots]
    c["planted"] = all("Changed" in o for o in out)
    c["plant_msg"] = out[0][:60]


def read(c):
    cx, cz = c["cx"], c["cz"]
    still = "passed" in rcon(f"execute if block {cx} {SAPLING_Y} {cz} minecraft:{c['sap']}")
    seen = {}
    if not still:
        for sp in SPECIES:
            n = filled(f"fill {cx-R} {Y_FLOOR} {cz-R} {cx+R} {Y_TOP} {cz+R} minecraft:air replace #minecraft:{sp}_logs")
            if n:
                seen[sp + "_logs"] = n
        for lv in LEAVES:
            n = filled(f"fill {cx-R} {Y_FLOOR} {cz-R} {cx+R} {Y_TOP} {cz+R} minecraft:air replace minecraft:{lv}")
            if n:
                seen[lv] = n
    rcon(f"fill {cx-R} {Y_FLOOR} {cz-R} {cx+R} {Y_TOP} {cz+R} minecraft:air")
    c["grown"] = not still and bool(seen)
    c["seen"] = seen
    return c


def verdict(c):
    seen = c["seen"]
    if not c.get("planted"):
        return "NOT PLANTED"
    if c["label"] == "control":
        if c["grows"]:
            return "ok" if c["grown"] else "CONTROL FAILED"
        return "ok (correctly no growth)" if not c["grown"] else "CONTROL GREW"
    if not c["grown"]:
        return "NO GROWTH"
    logs = {k[:-5] for k in seen if k.endswith("_logs")}
    leaves = {k for k in seen if k.endswith("_leaves")}
    extra = sorted((logs - c["logs"]) | (leaves - c["leaves"]))
    return "ok" if not extra else "UNEXPECTED " + ",".join(extra)


def main():
    cases = build_cases()
    where = place_grid(cases)
    if where is None:
        print("STOP: could not read a player position. Is a player logged in?")
        return
    print(f"grid centred on the player at {where[0]},{where[1]}", flush=True)
    rows = (len(cases) + COLS - 1) // COLS
    print(f"{len(cases)} cells in a {COLS}x{rows} grid, one rcon command at a time", flush=True)

    # Time must be moving or nothing can grow.
    def gametime():
        m = re.search(r"(\d+)", rcon("time query gametime"))
        return int(m.group(1)) if m else 0
    a = gametime(); time.sleep(3); b = gametime()
    if b - a < 20:
        print(f"STOP: game time moved {b-a} ticks in 3 s. Is a player logged in? "
              "With nobody online the server pauses and nothing grows.")
        return
    print("season:", rcon("season set mid_spring"), flush=True)

    # The cells are inside the area a logged-in player keeps loaded. Say so
    # if any are not, rather than waiting.
    unloaded = [c for c in cases if "passed" not in rcon(f"execute if loaded {c['cx']} 100 {c['cz']}")]
    if unloaded:
        print(f"STOP: {len(unloaded)} of {len(cases)} cells are not in loaded chunks, e.g. "
              f"{unloaded[0]['cx']},{unloaded[0]['cz']}. The grid is wider than the loaded area. Lower the case count and retry.", flush=True)
        return
    print("all cells are in loaded chunks", flush=True)

    # Two waves, a checkerboard. These trees can be 25 blocks wide, and
    # cells are only CELL apart. Growing neighbours together lets one tree
    # spill into the next cell's read area and corrupt its counts. In a
    # checkerboard the nearest planted cell is CELL * 1.41 away, about 45.
    waves = [[c for i, c in enumerate(cases) if (i % COLS + i // COLS) % 2 == w] for w in (0, 1)]
    for n, wave in enumerate(waves, 1):
        for c in wave:
            setup(c)
        print(f"wave {n}/2: planted {len(wave)}. growing...", flush=True)
        rcon("gamerule random_tick_speed 3000")
        time.sleep(8)
        rcon("gamerule random_tick_speed 3")
        for c in wave:
            read(c)
            top = ", ".join(f"{k}x{v}" for k, v in sorted(c["seen"].items(), key=lambda x: -x[1])[:3])
            note = f"  [{c['plant_msg']}]" if not c.get("planted") else ""
            print(f"{verdict(c):26} {c['label']:7} {c['kind']:6} {c['sap']:20} {c['biome']:32} {top}{note}", flush=True)

    tally = {}
    for c in cases:
        v = verdict(c).split()[0]
        tally[v] = tally.get(v, 0) + 1
    print("\n" + ", ".join(f"{n} {k}" for k, n in sorted(tally.items())), flush=True)


if __name__ == "__main__":
    main()
