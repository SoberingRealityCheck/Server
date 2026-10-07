#!/usr/bin/env python3
"""Make saplings grow Terralith's trees, per biome.

Terralith builds its trees at worldgen only. It does not touch the
vanilla tree features that saplings grow from, so a planted sapling always
makes a plain vanilla tree. Treeplacer lets a datapack say which tree a
sapling grows into, by biome. This script writes that datapack from
Terralith's own files, so it can be re-run after a Terralith update.

    python3 tools/treeplacer_terralith.py            write the datapack
    python3 tools/treeplacer_terralith.py --report   print the mapping only

How it works, in plain steps:

  1. For each Terralith biome, read the placed features it generates in the
     two steps that hold trees: surface_structures and vegetal_decoration.
  2. Follow each one down through the random selectors until it reaches a
     configured feature of type minecraft:tree. Only those are used. A
     selector would scatter trees around the sapling. We want one tree
     at the sapling.
  3. Sort each tree by its trunk block into a sapling species, and by
     its trunk placer into single (1x1) or mega (2x2).
  4. Write one file per sapling: biome -> list of trees.

Treeplacer looks up a sapling like this (read from its source): block
override, block tag, exact biome id, biome tag, then "all_biomes". We only
use exact biome ids. A biome with no entry for a sapling falls back to
vanilla, and so do all 55 vanilla biomes in the world.

If a chosen tree cannot be placed (no room), Treeplacer does NOT fall back
to a vanilla tree. The sapling just stays. Vanilla behaves the same way
when a tree has no room.
"""
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
PACK = HERE / "server-overrides/world/datapacks/z-treeplacer-terralith"
OUT = PACK / "data/treeplacer_terralith/sapling_overrides"

# Which decoration steps hold trees. Step numbers are Minecraft's order:
# 4 surface_structures, 9 vegetal_decoration. Terralith puts most trees in
# 9. A few special ones (giant trees) sit in 4.
TREE_STEPS = (4, 9)

# Trunk block -> sapling species. The trunk tells us what the tree is
# made of, which is what a player expects from the sapling they planted.
# Anything not here (mushroom stems, a tree built from wool or a nether
# stem) is skipped. Those are not what a sapling should grow.
TRUNK_SPECIES = {
    "oak": "oak", "birch": "birch", "spruce": "spruce", "jungle": "jungle",
    "acacia": "acacia", "dark_oak": "dark_oak", "cherry": "cherry",
    "mangrove": "mangrove", "pale_oak": "pale_oak",
}
# Vanilla's azalea tree has an oak trunk, so by trunk it would count as an
# oak. It belongs to the azalea sapling, which we leave on vanilla. Skip it.
# Terralith's own trees with azalea leaves are different. They are ordinary
# oak, jungle, acacia and dark oak trunks dressed with flowering leaves,
# which is just how that biome looks. They stay with their trunk species.
SKIP_FEATURES = {"minecraft:azalea_tree"}

# Species -> the sapling blocks that should use it. Mangrove grows from a
# propagule, not a sapling.
SAPLINGS = {
    "oak": ["oak_sapling"], "birch": ["birch_sapling"],
    "spruce": ["spruce_sapling"], "jungle": ["jungle_sapling"],
    "acacia": ["acacia_sapling"], "dark_oak": ["dark_oak_sapling"],
    "cherry": ["cherry_sapling"], "pale_oak": ["pale_oak_sapling"],
    "mangrove": ["mangrove_propagule"],
}

# Trunk placers that make a 2x2 trunk. Treeplacer uses a separate "mega"
# folder for saplings planted in a 2x2 square.
MEGA_PLACERS = {"giant_trunk_placer", "mega_jungle_trunk_placer", "dark_oak_trunk_placer"}

# A tree this short is a bush, not a tree. A planted oak should not give
# you a one-block shrub when taller trees exist in that biome. Anything
# with a maximum trunk height of 2 or less is dropped. Terralith's bushes
# are all height 1. Its smallest real tree is 3.
MIN_HEIGHT = 3

# Vanilla trees that carry bee nests. Vanilla's own sapling code picks the
# bee version only when flowers are nearby. A mapping that always picked
# it would put a nest on every tree. Swap each for the plain tree.
NO_BEES = {
    "minecraft:oak_bees_005": "minecraft:oak",
    "minecraft:fancy_oak_bees": "minecraft:fancy_oak",
    "minecraft:fancy_oak_bees_005": "minecraft:fancy_oak",
    "minecraft:cherry_bees_005": "minecraft:cherry",
    "minecraft:super_birch_bees": "minecraft:birch",
}


class Data:
    """Worldgen files, Terralith first. Terralith overrides some vanilla
    files of the same name, and those must win."""

    def __init__(self, terralith_jar, vanilla_jar):
        self.zips = [zipfile.ZipFile(terralith_jar), zipfile.ZipFile(vanilla_jar)]

    def get(self, kind, ident):
        ns, path = ident.split(":") if ":" in ident else ("minecraft", ident)
        name = f"data/{ns}/worldgen/{kind}/{path}.json"
        for z in self.zips:
            try:
                return json.loads(z.read(name))
            except KeyError:
                pass
        return None

    def biomes(self):
        out = {}
        for f in self.zips[0].namelist():
            m = re.match(r"data/terralith/worldgen/biome/(.+)\.json$", f)
            if m:
                out["terralith:" + m.group(1)] = json.loads(self.zips[0].read(f))
        return out


def trees_from_configured(data, cf, seen):
    """Every minecraft:tree configured feature reachable from cf."""
    if isinstance(cf, str):
        if cf in seen:
            return set()
        seen.add(cf)
        d = data.get("configured_feature", cf)
        if d is None:
            return set()
        if d["type"] == "minecraft:tree":
            return {cf}
        return trees_from_configured(data, d, seen)
    kind, conf = cf.get("type"), cf.get("config", {})
    out = set()
    if kind == "minecraft:random_selector":
        for e in conf.get("features", []):
            out |= trees_from_placed(data, e["feature"], seen)
        if conf.get("default"):
            out |= trees_from_placed(data, conf["default"], seen)
    elif kind == "minecraft:simple_random_selector":
        for e in conf.get("features", []):
            out |= trees_from_placed(data, e, seen)
    elif kind == "minecraft:random_boolean_selector":
        out |= trees_from_placed(data, conf["feature_true"], seen)
        out |= trees_from_placed(data, conf["feature_false"], seen)
    return out


def trees_from_placed(data, pf, seen):
    if isinstance(pf, str):
        if "P:" + pf in seen:
            return set()
        seen.add("P:" + pf)
        d = data.get("placed_feature", pf)
        return trees_from_configured(data, d["feature"], seen) if d else set()
    return trees_from_configured(data, pf["feature"], seen)


def block_names(provider):
    """The block names a state provider can produce."""
    if provider is None:
        return []
    kind = provider.get("type", "")
    if kind in ("minecraft:simple_state_provider", "minecraft:rotated_block_provider"):
        return [provider["state"]["Name"]]
    if kind == "minecraft:weighted_state_provider":
        return [e["data"]["Name"] for e in provider["entries"]]
    if kind == "minecraft:randomized_int_state_provider":
        return block_names(provider["source"])
    return []


def classify(data, feature):
    """(species, is_mega, max_height) for a tree feature, or None to skip it."""
    d = data.get("configured_feature", feature)
    c = d["config"]
    trunk = block_names(c.get("trunk_provider"))
    placer = c["trunk_placer"]
    height = placer.get("base_height", 0) + placer.get("height_rand_a", 0) + placer.get("height_rand_b", 0)

    species = None
    for t in trunk:
        # oak_log, stripped_oak_log, oak_wood and so on -> "oak"
        m = re.match(r"minecraft:(?:stripped_)?(.+?)(?:_log|_wood)$", t)
        if m and m.group(1) in TRUNK_SPECIES:
            species = TRUNK_SPECIES[m.group(1)]
            break
    if species is None:
        return None
    is_mega = placer["type"].replace("minecraft:", "") in MEGA_PLACERS
    return species, is_mega, height


def build(data):
    """{(sapling block, 'single'|'mega'): {biome: [features]}} plus a report."""
    mapping = defaultdict(lambda: defaultdict(list))
    skipped = defaultdict(set)
    for biome, d in sorted(data.biomes().items()):
        # Cave biomes: trees there are spider eggs and mushrooms, and
        # nobody plants a sapling in a cave.
        if biome.startswith("terralith:cave/"):
            continue
        found = set()
        for step in TREE_STEPS:
            if step < len(d["features"]):
                for pf in d["features"][step]:
                    found |= trees_from_placed(data, pf, set())
        found -= SKIP_FEATURES
        by_group = defaultdict(set)
        for f in found:
            info = classify(data, f)
            if info is None:
                skipped[biome].add(f)
                continue
            species, is_mega, height = info
            if height < MIN_HEIGHT:
                continue
            by_group[(species, "mega" if is_mega else "single")].add(NO_BEES.get(f, f))
        for (species, kind), feats in by_group.items():
            for sapling in SAPLINGS[species]:
                mapping[(sapling, kind)][biome] = sorted(feats)
    return mapping, skipped


def write(mapping):
    for old in OUT.rglob("*.json") if OUT.exists() else []:
        old.unlink()
    for (sapling, kind), biomes in sorted(mapping.items()):
        path = OUT / kind / "minecraft" / f"{sapling}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        values = {b: [{"feature": f, "weight": 1} for f in feats]
                  for b, feats in sorted(biomes.items())}
        path.write_text(json.dumps({"replace": False, "values": values}, indent=2) + "\n")
    (PACK / "pack.mcmeta").write_text(json.dumps({"pack": {
        "description": "Saplings grow Terralith's trees, by biome",
        "min_format": 88, "max_format": 107.1}}, indent=4) + "\n")


def report(mapping, skipped):
    print(f"{'sapling':22} {'kind':7} biomes  trees")
    for (sapling, kind), biomes in sorted(mapping.items()):
        n = len({f for fs in biomes.values() for f in fs})
        print(f"{sapling:22} {kind:7} {len(biomes):5}  {n:5}")
    covered = {b for biomes in mapping.values() for b in biomes}
    print(f"\n{len(covered)} Terralith biomes have at least one mapped sapling")
    if skipped:
        print("\nTrees skipped (not a normal wood tree):")
        for b, fs in sorted(skipped.items()):
            print(f"  {b}: {sorted(fs)}")


if __name__ == "__main__":
    terralith = next((ROOT / "data/mods").glob("Terralith*.jar"))
    vanilla = ROOT / "data/versions/26.2/server-26.2.jar"
    data = Data(terralith, vanilla)
    mapping, skipped = build(data)
    report(mapping, skipped)
    if "--report" not in sys.argv:
        write(mapping)
        files = sum(1 for _ in OUT.rglob("*.json"))
        print(f"\nwrote {files} sapling files to {OUT.relative_to(HERE)}")
