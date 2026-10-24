"""Regional biome variants: definitions and generator.

A variant is a child of a parent biome in one or more pack regions (regions.py). It inherits everything from
its parent at runtime (tags, spawns, carvers, features after every mod's changes, surface rules, key and list
checks; see Variants.java). It declares only what differs: colours and effects, attributes, and a feature patch.
Temperature, downfall and precipitation always stay the parent's, so seasons and snow behave the same.

Edit VARIANTS, then run:
  python3 variants/biome_variants.py SERVER_JAR TERRALITH_JAR      # writes src/main/resources/...
  python3 variants/biome_variants.py SERVER_JAR TERRALITH_JAR --check

Feature patch: "remove" names placed features of the parent; "add" names existing placed features, which are
copied under elysium:variant/<namespace>/<path> and appended to the step, so feature order stays acyclic.
"""
import json, os, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "src", "main", "resources")
sys.path.insert(0, HERE)
from regions import REGIONS

FOREST_ATTRS = "minecraft:forest"   # plain overworld sky, fog and music, for variants of stylized parents

VARIANTS = {
    # ---- Alps
    "alpine_pasture": {"parent": "minecraft:meadow", "regions": ["western_alps"], "name": "Alpine Pasture",
        "effects": {"grass_color": "#74b85a", "foliage_color": "#5aa040"},
        "why": "Western Alpine hay meadows: wetter and greener than the vanilla meadow."},
    "tyrolean_meadow": {"parent": "minecraft:meadow", "regions": ["eastern_alps"], "name": "Tyrolean Meadow",
        "effects": {"grass_color": "#8cb860", "foliage_color": "#6aa540"},
        "why": "Eastern Alps are drier and sunnier in summer: a warmer, yellower green."},
    "spruce_fir_slopes": {"parent": "minecraft:windswept_forest", "regions": ["western_alps"], "name": "Spruce-Fir Slopes",
        "effects": {"grass_color": "#6fa05c", "foliage_color": "#3f7a3f"},
        "why": "Dense dark spruce and silver fir on the wetter western flank."},
    "larch_slopes": {"parent": "minecraft:windswept_forest", "regions": ["eastern_alps"], "name": "Larch Slopes",
        "effects": {"grass_color": "#86ad6a", "foliage_color": "#8aa843"},
        "why": "Larch and Swiss pine stands: light, open, yellow-green canopy."},
    # ---- Western and Atlantic Europe
    "beech_oak_forest": {"parent": "minecraft:forest", "regions": ["west_european"], "name": "Beech-Oak Forest",
        "effects": {"grass_color": "#79bd58", "foliage_color": "#6fb83a"},
        "add": {"vegetal_decoration": ["minecraft:patch_leaf_litter"]},
        "why": "Beech and oak woods of the Jura, Vosges and Black Forest: fresh green canopy, deep leaf litter."},
    "hay_meadow": {"parent": "minecraft:meadow", "regions": ["west_european", "central_european"], "name": "Hay Meadow",
        "effects": {"grass_color": "#8ac35e", "foliage_color": "#62a843"},
        "add": {"vegetal_decoration": ["minecraft:flower_plains"]},
        "why": "Lowland hay meadows gone wild: tall grass and many flowers."},
    "atlantic_woodland": {"parent": "minecraft:birch_forest", "regions": ["atlantic"], "name": "Atlantic Woodland",
        "effects": {"grass_color": "#5fae4f", "foliage_color": "#4f9a38"},
        "add": {"vegetal_decoration": ["minecraft:patch_large_fern"]},
        "why": "Oceanic oak-birch woods: wet, mossy, ferny, deep green."},
    "atlantic_heath": {"parent": "terralith:brushland", "regions": ["atlantic"], "name": "Atlantic Heath",
        "effects": {"grass_color": "#8f9a5a", "foliage_color": "#6d7d3a", "dry_foliage_color": "#7d6a44"},
        "why": "Gorse and heather heath on poor soils near the coast: olive, not the brushland's sun-bleached yellow."},
    "atlantic_pasture": {"parent": "minecraft:plains", "regions": ["atlantic"], "name": "Atlantic Pasture",
        "effects": {"grass_color": "#6cc04f", "foliage_color": "#59ae30"},
        "why": "Rain-fed grassland: the greenest open land in Europe."},
    # ---- Po and Mediterranean
    "po_floodplain": {"parent": "minecraft:swamp", "regions": ["po_plain"], "name": "Po Floodplain",
        "effects": {"grass_color": "#82b55a", "foliage_color": "#6ea33a", "grass_color_modifier": "none", "water_color": "#3f76e4"},
        "remove": ["minecraft:trees_swamp"],
        "add": {"vegetal_decoration": ["minecraft:trees_birch_and_oak_leaf_litter", "minecraft:patch_tall_grass"]},
        "why": "Former rice and poplar country: wet meadows and riverside woods, not a murky swamp."},
    "poplar_wood": {"parent": "minecraft:birch_forest", "regions": ["po_plain"], "name": "Poplar Wood",
        "effects": {"grass_color": "#8fb85a", "foliage_color": "#7fb04a"},
        "why": "Escaped poplar plantations along the old field grid: pale, silvery green."},
    "holm_oak_forest": {"parent": "minecraft:forest", "regions": ["mediterranean"], "name": "Holm Oak Forest",
        "effects": {"grass_color": "#a3ad5b", "foliage_color": "#4d6b34", "dry_foliage_color": "#8a7040"},
        "why": "Evergreen holm oak: dark grey-green canopy over dry grass."},
    "garrigue": {"parent": "minecraft:meadow", "regions": ["mediterranean"], "name": "Garrigue",
        "effects": {"grass_color": "#b0ad62", "foliage_color": "#6f7f3d"},
        "add": {"vegetal_decoration": ["minecraft:patch_dry_grass_desert"]},
        "why": "Low aromatic scrub and dry grass on limestone."},
    "maquis": {"parent": "terralith:sakura_grove", "regions": ["mediterranean"], "name": "Maquis", "attributes_from": FOREST_ATTRS,
        "effects": {"grass_color": "#a7a75c", "foliage_color": "#556f35", "dry_foliage_color": "#8a7040"},
        "remove": ["terralith:sakura/cherry_trees", "terralith:sakura/cherry_trees_light", "terralith:sakura/bamboo", "terralith:sakura/flowers"],
        "add": {"vegetal_decoration": ["minecraft:trees_plains", "minecraft:patch_bush"]},
        "why": "The base map puts sakura here. Mediterranean scrub keeps its shape but drops the cherry trees and bamboo."},
    "apennine_beech": {"parent": "terralith:sakura_grove", "regions": ["apennines", "dinaric"], "name": "Montane Beech Wood", "attributes_from": FOREST_ATTRS,
        "effects": {"grass_color": "#79c05a", "foliage_color": "#6aac3c", "dry_foliage_color": "#7b5334"},
        "remove": ["terralith:sakura/cherry_trees", "terralith:sakura/cherry_trees_light", "terralith:sakura/bamboo", "terralith:sakura/flowers"],
        "add": {"vegetal_decoration": ["minecraft:trees_birch_and_oak_leaf_litter"]},
        "why": "Apennine and Dinaric beech belts. Replaces the base map's sakura."},
    "karst_highlands": {"parent": "terralith:temperate_highlands", "regions": ["dinaric"], "name": "Karst Highlands",
        "effects": {"grass_color": "#95a868", "foliage_color": "#5d8a3c"},
        "why": "Thin soil on limestone: grey-green grass, scattered trees."},
}


class Sources:
    def __init__(self, *jars): self.z = [zipfile.ZipFile(j) for j in jars]
    def get(self, kind, ident):
        ns, path = ident.split(":")
        for z in self.z:
            try: return json.loads(z.read(f"data/{ns}/worldgen/{kind}/{path}.json"))
            except KeyError: pass
        raise SystemExit(f"no {kind} {ident} in the given jars")


def wrapped(ident):
    ns, path = ident.split(":"); return f"elysium:variant/{ns}/{path}"


def generate(src, check=False):
    regions = set(REGIONS); out = {}; placed = {}; lang = {}; table = {}; claims = {}
    for name, v in VARIANTS.items():
        vid = f"elysium:{name}"; parent = src.get("biome", v["parent"])
        for r in v["regions"]:
            if r not in regions: raise SystemExit(f"{vid}: unknown region {r}")
            k = (r, v["parent"])
            if k in claims: raise SystemExit(f"{vid} and {claims[k]} both replace {v['parent']} in {r}")
            claims[k] = vid
        steps = [s for s in parent["features"]]
        present = {f for s in steps for f in s}
        for f in v.get("remove", []):
            if f not in present: raise SystemExit(f"{vid}: parent {v['parent']} has no feature {f} to remove")
        b = dict(parent)
        b["effects"] = {**parent.get("effects", {}), **v.get("effects", {})}
        if b["effects"].get("grass_color_modifier") == "none": del b["effects"]["grass_color_modifier"]
        if "attributes_from" in v: b["attributes"] = src.get("biome", v["attributes_from"]).get("attributes", {})
        out[f"data/elysium/worldgen/biome/{name}.json"] = b
        add = {}
        for step, ids in v.get("add", {}).items():
            add[step] = []
            for f in ids:
                placed[f"data/elysium/worldgen/placed_feature/variant/{f.split(':')[0]}/{f.split(':')[1]}.json"] = src.get("placed_feature", f)
                add[step].append(wrapped(f))
        table[vid] = {"parent": v["parent"], "regions": v["regions"], "add_features": add, "remove_features": v.get("remove", []), "why": v["why"]}
        lang[f"biome.elysium.{name}"] = v["name"]
    files = {**out, **placed,
             "assets/elysium/lang/en_us.json": lang,
             "elysium_atlas/variants.json": {"format": 1, "generated_by": "variants/biome_variants.py", "variants": table}}
    if check:
        stale = [p for p, d in files.items() if not os.path.exists(os.path.join(RES, p)) or json.load(open(os.path.join(RES, p))) != d]
        print("stale:" if stale else "up to date", *stale); return not stale
    for p, d in files.items():
        f = os.path.join(RES, p); os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh: json.dump(d, fh, indent=2); fh.write("\n")
    print(f"{len(VARIANTS)} variants, {len(placed)} copied placed features")
    return True


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    ok = generate(Sources(*a), check="--check" in sys.argv)
    sys.exit(0 if ok else 1)
