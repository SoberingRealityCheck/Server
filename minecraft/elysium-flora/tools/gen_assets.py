"""Write elysium_flora's generated resources: blockstates, models, item definitions, lang, loot tables,
recipes, tags and the test tree features. Run from anywhere; it writes into ../src/main/resources.

Everything for a wood comes from its vanilla log: textures are the log's own side and top (cropped by UV),
so resource packs that retexture logs also retexture thin logs. Edit this script, not the JSON it writes.

    python3 tools/gen_assets.py
"""
import json
import shutil
from pathlib import Path

NS = "elysium_flora"
RES = Path(__file__).resolve().parent.parent / "src" / "main" / "resources"

# (wood, planks). Same order as ElysiumFlora.WOODS. No pale oak.
WOODS = [("oak", "oak_planks"), ("spruce", "spruce_planks"), ("birch", "birch_planks"),
         ("jungle", "jungle_planks"), ("acacia", "acacia_planks"), ("dark_oak", "dark_oak_planks"),
         ("mangrove", "mangrove_planks"), ("cherry", "cherry_planks")]

DIRS = ["north", "south", "east", "west", "up", "down"]
OPP = {"north": "south", "south": "north", "east": "west", "west": "east", "up": "down", "down": "up"}

# Arms: 6 px square, 5 px long, from the core (5..11) to the block face. No end face: an arm only exists
# when something is joined there, which covers it.
ARM_BOX = {
    "north": ([5, 5, 0], [11, 11, 5]), "south": ([5, 5, 11], [11, 11, 16]),
    "west": ([0, 5, 5], [5, 11, 11]), "east": ([11, 5, 5], [16, 11, 11]),
    "down": ([5, 0, 5], [11, 5, 11]), "up": ([5, 11, 5], [11, 16, 11]),
}
# A 6 x 5 strip of bark. The log side texture's grain runs along v; rotate it 90 where the arm runs across v.
STRIP = [5, 0, 11, 5]


def arm_faces(d):
    faces = {}
    for f in DIRS:
        if f in (d, OPP[d]):
            continue
        face = {"uv": STRIP, "texture": "#side"}
        if d in ("east", "west"):
            face["rotation"] = 90          # every side face of an x arm has u along x
        elif d in ("north", "south") and f in ("east", "west"):
            face["rotation"] = 90          # side faces of a z arm have u along z; top and bottom have v along z
        faces[f] = face
    return faces


def cap(d, texture):
    """One face of the 6 px core, shown when nothing is joined on that side."""
    return {"parent": "minecraft:block/block", "textures": {"particle": "#side"},
            "elements": [{"from": [5, 5, 5], "to": [11, 11, 11],
                          "faces": {d: {"uv": [5, 5, 11, 11], "texture": texture}}}]}


def write(path, obj):
    p = RES / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n")


def templates():
    for d in DIRS:
        write(f"assets/{NS}/models/block/template_thin_log_arm_{d}.json", {
            "parent": "minecraft:block/block", "textures": {"particle": "#side"},
            "elements": [{"from": ARM_BOX[d][0], "to": ARM_BOX[d][1], "faces": arm_faces(d)}]})
        write(f"assets/{NS}/models/block/template_thin_log_cap_{d}_bark.json", cap(d, "#side"))
        write(f"assets/{NS}/models/block/template_thin_log_cap_{d}_end.json", cap(d, "#end"))
    # Inventory and hand: an upright pole.
    write(f"assets/{NS}/models/block/template_thin_log_item.json", {
        "parent": "minecraft:block/block", "textures": {"particle": "#side"},
        "elements": [{"from": [5, 0, 5], "to": [11, 16, 11], "faces": {
            "north": {"uv": [5, 0, 11, 16], "texture": "#side"}, "south": {"uv": [5, 0, 11, 16], "texture": "#side"},
            "east": {"uv": [5, 0, 11, 16], "texture": "#side"}, "west": {"uv": [5, 0, 11, 16], "texture": "#side"},
            "up": {"uv": [5, 5, 11, 11], "texture": "#end"}, "down": {"uv": [5, 5, 11, 11], "texture": "#end"}}}]})


def blockstate(name):
    parts = []
    for d in DIRS:
        parts.append({"when": {d: "true"}, "apply": {"model": f"{NS}:block/{name}_arm_{d}"}})
        # A free face shows end grain when the log runs through it (the tip of a pole or branch), bark otherwise.
        parts.append({"when": {d: "false", OPP[d]: "true"}, "apply": {"model": f"{NS}:block/{name}_cap_{d}_end"}})
        parts.append({"when": {d: "false", OPP[d]: "false"}, "apply": {"model": f"{NS}:block/{name}_cap_{d}_bark"}})
    return {"multipart": parts}


def thin_log(log, planks, lang):
    name = f"thin_{log}"
    tex = {"side": f"minecraft:block/{log}", "end": f"minecraft:block/{log}_top"}
    for d in DIRS:
        write(f"assets/{NS}/models/block/{name}_arm_{d}.json",
              {"parent": f"{NS}:block/template_thin_log_arm_{d}", "textures": tex})
        for kind in ("bark", "end"):
            write(f"assets/{NS}/models/block/{name}_cap_{d}_{kind}.json",
                  {"parent": f"{NS}:block/template_thin_log_cap_{d}_{kind}", "textures": tex})
    write(f"assets/{NS}/models/block/{name}_item.json",
          {"parent": f"{NS}:block/template_thin_log_item", "textures": tex})
    write(f"assets/{NS}/blockstates/{name}.json", blockstate(name))
    write(f"assets/{NS}/items/{name}.json",
          {"model": {"type": "minecraft:model", "model": f"{NS}:block/{name}_item"}})
    lang[f"block.{NS}.{name}"] = "Thin " + log.replace("_", " ").title()

    write(f"data/{NS}/loot_table/blocks/{name}.json", {
        "type": "minecraft:block", "random_sequence": f"{NS}:blocks/{name}",
        "pools": [{"rolls": 1.0, "bonus_rolls": 0.0, "conditions": [{"condition": "minecraft:survives_explosion"}],
                   "entries": [{"type": "minecraft:item", "name": f"{NS}:{name}"}]}]})

    # 1:1 both ways. A lone log already makes planks, so the swap takes two stacked (fits the 2x2 grid).
    write(f"data/{NS}/recipe/{name}_from_{log}.json", {
        "type": "minecraft:crafting_shaped", "category": "building", "group": "thin_logs",
        "key": {"#": f"minecraft:{log}"}, "pattern": ["#", "#"], "result": {"id": f"{NS}:{name}", "count": 2}})
    write(f"data/{NS}/recipe/{log}_from_{name}.json", {
        "type": "minecraft:crafting_shaped", "category": "building", "group": "thin_logs",
        "key": {"#": f"{NS}:{name}"}, "pattern": ["#", "#"], "result": {"id": f"minecraft:{log}", "count": 2}})
    # Same planks as a full log.
    write(f"data/{NS}/recipe/{planks}_from_{name}.json", {
        "type": "minecraft:crafting_shapeless", "category": "building", "group": "planks",
        "ingredients": [f"{NS}:{name}"], "result": {"id": f"minecraft:{planks}", "count": 4}})
    return f"{NS}:{name}"


def tags(ids):
    # Block #logs: leaves next to a thin log do not decay, axes mine it fast, and full logs join it.
    for t in ("logs", "logs_that_burn"):
        write(f"data/minecraft/tags/block/{t}.json", {"replace": False, "values": ids})
        # Item #logs and #logs_that_burn: fuel and charcoal. Not #oak_logs etc., which would add a planks recipe.
        write(f"data/minecraft/tags/item/{t}.json", {"replace": False, "values": ids})
    write("data/minecraft/tags/block/mineable/axe.json", {"replace": False, "values": ids})


# --- test trees ---------------------------------------------------------------------------------
def leaves(block):
    return {"type": "minecraft:simple_state_provider",
            "state": {"Name": f"minecraft:{block}",
                      "Properties": {"distance": "7", "persistent": "false", "waterlogged": "false"}}}


def simple(block, props=None):
    s = {"Name": block}
    if props:
        s["Properties"] = props
    return {"type": "minecraft:simple_state_provider", "state": s}


BELOW_TRUNK = {"type": "minecraft:rule_based_state_provider", "rules": [{
    "if_true": {"type": "minecraft:not", "predicate": {"type": "minecraft:matching_block_tag",
                                                      "tag": "minecraft:cannot_replace_below_tree_trunk"}},
    "then": {"type": "minecraft:simple_state_provider", "state": {"Name": "minecraft:dirt"}}}]}
CONNECT = {"type": f"{NS}:connect_thin_logs"}


def tree(trunk, trunk_placer, foliage, foliage_placer, decorators):
    return {"type": "minecraft:tree", "config": {
        "below_trunk_provider": BELOW_TRUNK, "trunk_provider": trunk, "trunk_placer": trunk_placer,
        "foliage_provider": leaves(foliage), "foliage_placer": foliage_placer,
        "minimum_size": {"type": "minecraft:two_layers_feature_size", "limit": 1, "lower_size": 0, "upper_size": 1},
        "decorators": decorators, "ignore_vines": True}}


def multi_stem(base, rand_a, stems, spread, lean, fork):
    return {"type": f"{NS}:multi_stem", "base_height": base, "height_rand_a": rand_a, "height_rand_b": 0,
            "stems": stems, "spread": spread, "lean": lean, "fork_chance": fork}


def stubs(block, p, min_frac, length, rise):
    return {"type": f"{NS}:branch_stubs", "block": simple(f"{NS}:{block}"), "probability": p,
            "min_height_fraction": min_frac, "length": length, "rise_chance": rise}


def uniform(lo, hi):
    return {"type": "minecraft:uniform", "min_inclusive": lo, "max_inclusive": hi}


TREES = {
    # Honey mesquite (Prosopis glandulosa): 2-4 crooked stems from one root, a low flat open crown.
    "honey_mesquite": tree(simple(f"{NS}:thin_acacia_log"), multi_stem(3, 2, uniform(2, 4), 0, 0.5, 0.3),
                           "acacia_leaves", {"type": "minecraft:acacia_foliage_placer", "radius": 2, "offset": 0},
                           [CONNECT]),
    # Quaking aspen (Populus tremuloides): one tall straight pole, a small high crown, a few twigs below it.
    "quaking_aspen": tree(simple(f"{NS}:thin_birch_log"), multi_stem(8, 4, 1, 0, 0.08, 0.0),
                          "birch_leaves", {"type": "minecraft:blob_foliage_placer", "radius": 2, "offset": 0, "height": 4},
                          [stubs("thin_birch_log", 0.25, 0.5, 1, 0.3), CONNECT]),
    # Grey alder / hazel clump: 3-5 thin stems from a 3x3 stool, each with its own small leaf clump.
    "alder_clump": tree(simple(f"{NS}:thin_oak_log"), multi_stem(4, 2, uniform(3, 5), 1, 0.35, 0.2),
                        "oak_leaves", {"type": "minecraft:blob_foliage_placer", "radius": 1, "offset": 0, "height": 2},
                        [CONNECT]),
    # A vanilla-sized oak (full log trunk) with thin side branches below and through the crown.
    "oak_with_branches": tree(simple("minecraft:oak_log", {"axis": "y"}),
                              {"type": "minecraft:straight_trunk_placer", "base_height": 5, "height_rand_a": 2,
                               "height_rand_b": 0},
                              "oak_leaves", {"type": "minecraft:blob_foliage_placer", "radius": 2, "offset": 0, "height": 3},
                              [stubs("thin_oak_log", 0.4, 0.3, 2, 0.5)]),
}


def main():
    for sub in ("assets", "data"):
        shutil.rmtree(RES / sub, ignore_errors=True)
    templates()
    lang, ids = {}, []
    for wood, planks in WOODS:
        for log in (f"{wood}_log", f"stripped_{wood}_log"):
            ids.append(thin_log(log, planks, lang))
    tags(ids)
    write(f"assets/{NS}/lang/en_us.json", dict(sorted(lang.items())))
    for name, feature in TREES.items():
        write(f"data/{NS}/worldgen/configured_feature/{name}.json", feature)
    print(f"{len(ids)} thin logs, {len(TREES)} test trees -> {RES}")


if __name__ == "__main__":
    main()
