#!/usr/bin/env python3
"""Teach Serene Seasons about Terralith's biomes.

Serene Seasons sorts biomes with four tags that only list vanilla
biomes. This file is the source of truth for the tag files in
server-overrides/world/datapacks/z-seasons-terralith. JSON can't hold
comments, so the reasoning lives here, next to each biome.

    python3 tools/seasons_terralith.py                 write the tag files
    python3 tools/seasons_terralith.py --audit [JAR]   print every Terralith
                                                       biome and what it gets,
                                                       and flag new ones

What each tag does (read from Serene Seasons' bytecode, not its docs):

  blacklisted  Immune. Raw biome temperature, no seasonal snow or ice,
               no foliage color change, crops fertile all year.
  tropical     Fixed warm temperature, so never snow. Wet and dry
               seasons instead. Crops follow summer rules all year.
  lesser       Milder foliage color change. Does nothing for snow.
  (no tag)     Full seasons. Winter subtracts 0.8 from the temperature,
               but only for biomes with a base temperature of 0.8 or
               lower. Every other season adds nothing. So cold biomes stay
               cold all year, and only winter changes anything.

Temperature is all or nothing per biome. There is no "smaller winter".
The only per-biome dial is the color one, and it is weak.

A biome can sit in more than one list. Tropical and blacklisted together
is what vanilla does for warm_ocean, and we copy it for deep_warm_ocean.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PACK = HERE / "server-overrides/world/datapacks/z-seasons-terralith"
TAG_DIR = PACK / "data/sereneseasons/tags/worldgen/biome"

# --- Blacklisted: fully immune -----------------------------------------

# Entries here are biome tags (#...) or full ids. Tags are fine in this
# list because I read every member and all of them belong.
BLACKLISTED = [
    # Vanilla blacklists rivers, beaches and caves. We match it.
    # c:is_river holds only warm_river (base temp 0.5). Without this it
    # would freeze solid in winter while vanilla rivers stay liquid.
    "#c:is_river",
    # c:is_beach holds only gravel_beach (0.8). Same reason as rivers.
    "#c:is_beach",
    # c:is_cave holds all 11 Terralith caves. Underground biomes have no
    # weather. The tag also picks up new caves from a Terralith update.
    "#c:is_cave",

    # Vanilla lists warm_ocean as both tropical and blacklisted. This is
    # the Terralith version. Base temp 0.5, so it would freeze in winter.
    "terralith:deep_warm_ocean",

    # The four season-themed floating islands. Their whole identity is one
    # fixed season, so they must not change with the real one.
    # A side effect worth knowing: crops are fertile all year here, so
    # the skylands work as permanent farmland.
    # skylands_winter has a raw temp of 0.2, which is above the 0.15
    # snow line. So it rains there, as it does in plain Terralith. Its
    # snow comes from its features, not from the weather. We keep that.
    "terralith:skylands_spring",
    "terralith:skylands_summer",
    "terralith:skylands_autumn",
    "terralith:skylands_winter",

    # Named winter, built as a fixed winter scene, raw temp 0.0 (so it
    # does snow). It is the twin of alpha_islands, which stays seasonal.
    # See "Judgement calls" in SEASONS_TERRALITH.md.
    "terralith:alpha_islands_winter",
]

# --- Tropical: warm all year, wet and dry seasons ----------------------

# Explicit ids on purpose. The shared c: tags look handy but are unsafe:
# c:is_badlands contains terralith:snowy_badlands (base temp 0). As
# tropical it would never snow. Explicit ids can't surprise us when
# Terralith updates. The cost is that new hot biomes need adding by hand,
# which --audit reports.
TROPICAL = [
    # Deserts. All have a base temp of 2.0 and no rain.
    "terralith:ancient_sands",
    "terralith:desert_canyon",
    "terralith:desert_oasis",
    "terralith:desert_spires",
    "terralith:lush_desert",
    "terralith:sandstone_valley",

    # Mesas and canyons. Base temp 2.0 except painted_mountains and
    # savanna_badlands (1.0).
    "terralith:bryce_canyon",
    "terralith:red_oasis",
    "terralith:white_mesa",
    "terralith:warped_mesa",         # Not in c:is_badlands, but a mesa.
    "terralith:savanna_badlands",
    "terralith:painted_mountains",   # Warm mesa-like mountains, temp 1.0.
    # NOT snowy_badlands. Base temp 0, so it must keep its winter.

    # Savannas and dry scrub. Temp 1.0 to 1.6, no rain.
    "terralith:arid_highlands",
    "terralith:ashen_savanna",
    "terralith:fractured_savanna",
    "terralith:savanna_slopes",
    "terralith:brushland",           # Not in any c: tag. Temp 1.2, no rain.
    "terralith:shrubland",           # Same.
    "terralith:hot_shrubland",       # Temp 0.8, so it WOULD snow without
                                     # this. A snowy hot shrubland is silly.

    # Jungles. Temp 0.95. They never cool in winter anyway, because
    # the cooling needs a base temp of 0.8 or lower. Tropical adds the
    # wet and dry seasons and the year-round crops that vanilla jungle has.
    "terralith:tropical_jungle",
    "terralith:rocky_jungle",
    "terralith:jungle_mountains",
    "terralith:amethyst_rainforest",
    "terralith:amethyst_canyon",

    # Vanilla mushroom_fields is tropical. mirage_isles is Terralith's
    # version of it (c:is_mushroom lists it), so it matches.
    "terralith:mirage_isles",

    # See the blacklist. Vanilla warm_ocean is in both lists.
    "terralith:deep_warm_ocean",
]

# --- Lesser color change: snow still comes, colors shift less ----------

# These biomes have a hand-picked, stylized palette. The full autumn and
# winter color shift would wash it out. Lesser keeps more of the original.
# Serene Seasons uses a 0.75 factor for it. I could not tell from the
# bytecode whether that is the share kept or the share changed, so treat
# the effect as "milder", not as a number.
LESSER_COLOR = [
    # Swamps. Vanilla swamp is the one vanilla entry in this list.
    "terralith:orchid_swamp",
    "terralith:ice_marsh",

    # Fantasy palettes. Pink, purple, night blue.
    "terralith:sakura_grove",
    "terralith:sakura_valley",
    "terralith:lavender_forest",
    "terralith:lavender_valley",
    "terralith:moonlight_grove",
    "terralith:moonlight_valley",
    "terralith:mirage_isles",
    "terralith:alpha_islands",

    # Tropical, but with a deliberate crystal or gem color scheme.
    "terralith:amethyst_canyon",
    "terralith:amethyst_rainforest",

    # Mountains with an odd grass color: red and green.
    "terralith:scarlet_mountains",
    "terralith:emerald_peaks",

    # Ash and fire colors.
    "terralith:volcanic_crater",
    "terralith:volcanic_peaks",
]

# Tropical biomes that are cold on purpose. The audit would flag them
# otherwise. Each one copies how vanilla treats its twin.
COLD_BUT_TROPICAL_ON_PURPOSE = {
    "terralith:deep_warm_ocean",  # vanilla warm_ocean is also temp 0.5
    "terralith:mirage_isles",     # vanilla mushroom_fields is tropical
}

TAGS = {
    "tropical_biomes": TROPICAL,
    "blacklisted_biomes": BLACKLISTED,
    "lesser_color_change_biomes": LESSER_COLOR,
}


def write_tags():
    TAG_DIR.mkdir(parents=True, exist_ok=True)
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {
        "description": "Teaches Serene Seasons about Terralith's biomes",
        "min_format": 88, "max_format": 107.1}}, indent=4) + "\n")
    for name, ids in TAGS.items():
        # required: false so the pack still loads if Terralith is removed.
        values = [{"id": i, "required": False} for i in ids]
        (TAG_DIR / f"{name}.json").write_text(
            json.dumps({"replace": False, "values": values}, indent=4) + "\n")
        print(f"wrote {name}: {len(ids)} entries")


# --- Audit -------------------------------------------------------------

def expand(z, tag, seen=None):
    """Resolve a tag (and tags inside it) to biome ids, from Terralith's jar."""
    seen = seen if seen is not None else set()
    if tag in seen:
        return set()
    seen.add(tag)
    ns, name = tag.lstrip("#").split(":")
    path = f"data/{ns}/tags/worldgen/biome/{name}.json"
    if path not in z.namelist():
        return set()
    out = set()
    for v in json.loads(z.read(path))["values"]:
        i = v if isinstance(v, str) else v["id"]
        out |= expand(z, i, seen) if i.startswith("#") else {i}
    return out


def resolve(z, entries):
    out = set()
    for e in entries:
        out |= expand(z, e) if e.startswith("#") else {e}
    return out


def audit(jar):
    z = zipfile.ZipFile(jar)
    biomes = {}
    for f in z.namelist():
        m = re.match(r"data/terralith/worldgen/biome/(.+)\.json$", f)
        if m:
            biomes["terralith:" + m.group(1)] = json.loads(z.read(f))

    black = resolve(z, BLACKLISTED)
    trop = set(TROPICAL)
    lesser = set(LESSER_COLOR)
    unknown = (black | trop | lesser) - set(biomes)
    if unknown:
        print("IDS IN THIS FILE THAT TERRALITH DOES NOT HAVE:", sorted(unknown))

    print(f"{len(biomes)} Terralith biomes\n")
    print(f"{'biome':36} {'temp':>5} {'rain':>4}  result")
    flagged = []
    for name, d in sorted(biomes.items(), key=lambda x: x[1]["temperature"]):
        t = d["temperature"]
        rain = "yes" if d.get("has_precipitation") else "no"
        if name in black and name in trop:
            what = "immune + tropical"
        elif name in black:
            what = "IMMUNE"
        elif name in trop:
            what = "tropical (never snows)"
        elif t <= 0.8:
            what = "full seasons, snows in winter"
        else:
            what = "full seasons, no winter snow (temp > 0.8)"
        if name in lesser:
            what += ", milder colors"
        print(f"{name:36} {t:>5} {rain:>4}  {what}")
        # Flag anything a human should look at: a hot biome left on
        # default, or a cold biome marked tropical.
        if name in trop and t < 0.8 and name not in COLD_BUT_TROPICAL_ON_PURPOSE:
            flagged.append(f"{name}: tropical but cold (temp {t})")
        if name not in black | trop and t >= 1.2:
            flagged.append(f"{name}: very hot (temp {t}) and not tropical")
    print(f"\n{len(black)} immune, {len(trop)} tropical, {len(lesser)} milder colors, "
          f"{len(set(biomes) - black - trop)} on full seasons")
    if flagged:
        print("\nLOOK AT THESE:")
        for f in flagged:
            print(" ", f)
    else:
        print("\nNothing flagged.")


if __name__ == "__main__":
    if "--audit" in sys.argv:
        rest = [a for a in sys.argv[2:] if not a.startswith("-")]
        jar = rest[0] if rest else next((HERE.parent / "data/mods").glob("Terralith*.jar"))
        audit(jar)
    else:
        write_tags()
