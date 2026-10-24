"""Per-biome local relief for the atlas: the small terms on top of the atlas height.

The atlas carries the large terms (real elevation, down to its cell size). Each biome adds its own small,
zero-mean relief in the mod (Detail.java): amplitude in blocks, base wavelength in blocks, and a style
  rolling   fractal noise (three octaves)
  ridged    sharp crests (dunes)
  terrace   soft steps (badlands, mesas)
Defaults come from the biome's traits (landform, cover, tags; biome_traits.json via placement.Niche); OVERRIDES
below is the tuning knob. Amplitudes are in blocks, so the table holds at any metres-per-block.

usage: python3 bake_detail.py ATLAS_DIR        adds "detail" to atlas.json
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from placement import Placement

FINE_LEVEL_FACTOR = 0.35    # under L1 (4-block cells) the atlas already carries real relief down to ~16 blocks
NONE = ("ocean", "river", "beach", "stony_shore")

# biome -> (amplitude blocks, wavelength blocks, style); wins over the defaults
OVERRIDES = {
    "minecraft:meadow": (2.5, 80, "rolling"),
    "minecraft:plains": (1.2, 120, "rolling"),
    "minecraft:sunflower_plains": (1.2, 120, "rolling"),
    "terralith:shield": (4.0, 50, "rolling"),            # glacial knobs and hollows
    "terralith:shield_clearing": (3.5, 50, "rolling"),
    "terralith:steppe": (1.5, 140, "rolling"),
    "biomesoplenty:prairie": (1.5, 140, "rolling"),
    "biomesoplenty:pasture": (1.5, 120, "rolling"),
    "wilderwild:flower_field": (1.8, 100, "rolling"),
    "terralith:moonlight_valley": (3.0, 60, "rolling"),
    "biomesoplenty:dune_beach": (3.0, 30, "ridged"),
    "minecraft:desert": (4.0, 40, "ridged"),
    "terralith:desert_oasis": (2.0, 60, "rolling"),
    "terralith:red_oasis": (2.0, 60, "rolling"),
}


def default(n):
    t = n.tags
    if n.wet: return (0.6, 48, "rolling")
    if t & {"c:is_badlands"} or n.landform == "mesa": return (6.0, 70, "terrace")
    if t & {"c:is_desert", "c:is_sandy"}: return (4.0, 40, "ridged")
    if n.landform in ("peak", "cliff", "mountain"): return (3.0, 40, "rolling")    # the atlas and Tectonic's jaggedness make the mountain
    if n.landform == "hill": return (7.0, 110, "rolling")
    if n.landform in ("highland", "plateau"): return (5.0, 90, "rolling")
    if n.snow: return (2.0, 90, "rolling")
    if n.cover >= 0.55: return (3.0, 70, "rolling")          # forest floor: knolls and hollows
    if n.cover < 0.2: return (1.5, 110, "rolling")           # open grass: long low swells
    return (2.5, 90, "rolling")


def main():
    adir = sys.argv[1]; mpath = os.path.join(adir, "atlas.json"); m = json.load(open(mpath))
    P = Placement(os.path.join(HERE, "data", "biome_traits.json")); niche = {n.id: n for n in P.niches}
    out = {}
    for b in m["biome_palette"]:
        if any(k in b for k in NONE): continue
        if b in OVERRIDES: out[b] = list(OVERRIDES[b])
        elif b in niche: out[b] = list(default(niche[b]))
        else: out[b] = [2.0, 80, "rolling"]
    m["detail"] = {"fine_level_factor": FINE_LEVEL_FACTOR, "seed": 7105380, "biomes": out,
                   "sources": "bake/bake_detail.py (biome traits + OVERRIDES)"}
    json.dump(m, open(mpath + ".part", "w"), indent=1); os.replace(mpath + ".part", mpath)
    styles = {}
    for v in out.values(): styles[v[2]] = styles.get(v[2], 0) + 1
    print(f"detail for {len(out)} biomes: {styles}")


if __name__ == "__main__":
    main()
