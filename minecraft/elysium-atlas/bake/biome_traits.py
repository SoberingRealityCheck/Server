"""Biome traits for scored placement, read from the pack's own jars.

For every overworld surface biome in vanilla, Terralith, Biomes O' Plenty, Wilder Wild and Terrestria:
  temperature, downfall, has_precipitation   from the biome JSON (Terralith's copy wins for minecraft:*,
                                              since Terralith replaces those files in the pack)
  tags                                        every c: and minecraft: biome tag that lists it, nested tags resolved
  trees                                       expected trees per chunk from its vegetal placed features
  terrain                                     landform the biome expects, from c:is_mountain/peak|slope, is_plateau,
                                              is_hill, is_windswept and a few name tokens (canyon, cliffs, spires ...)
Nothing here is chosen per biome by hand except the exclusion list and REALM below.

usage: python3 biome_traits.py OUT_JSON SERVER_JAR MOD_JAR...
"""
import json, math, re, sys, zipfile
from collections import defaultdict

out, server_jar, *mod_jars = sys.argv[1:]

# ---- read every data/ file from the jars (nested jars one level deep: Fabric API's convention tags)
files = {}            # (source, path) -> bytes; later sources do not overwrite earlier keys per path
order = []
def add_zip(z, src):
    for n in z.namelist():
        if n.startswith("data/") and n.endswith(".json"): files.setdefault(n, []).append((src, z.read(n)))
        elif n.startswith("META-INF/jars/") and n.endswith(".jar") and ("convention-tags" in n or "biolith" in n):
            import io
            add_zip(zipfile.ZipFile(io.BytesIO(z.read(n))), src + "!" + n.rsplit("/", 1)[1])
def open_jar(p):
    z = zipfile.ZipFile(p)
    inner = [n for n in z.namelist() if re.match(r"META-INF/versions/[^/]+/server-[^/]+\.jar$", n)]
    if inner:   # the server bundle
        import io
        return zipfile.ZipFile(io.BytesIO(z.read(inner[0])))
    return z
add_zip(open_jar(server_jar), "minecraft")
for p in mod_jars: add_zip(open_jar(p), p.rsplit("/", 1)[-1])

def load(path, prefer=("terralith",)):
    """The pack's effective copy: a Terralith override beats vanilla; otherwise the last source."""
    c = files.get(path)
    if not c: return None
    for s, b in c:
        if any(k in s.lower() for k in prefer): return json.loads(b)
    return json.loads(c[-1][1])
def rid(path, kind):
    m = re.match(rf"data/([^/]+)/{kind}/(.+)\.json$", path)
    return m and f"{m.group(1)}:{m.group(2)}"

# ---- tags: union over sources, nested references resolved
raw = defaultdict(set)
for path, copies in files.items():
    m = re.match(r"data/([^/]+)/tags/worldgen/biome/(.+)\.json$", path)
    if not m: continue
    for _, b in copies:
        for v in json.loads(b).get("values", []):
            raw[f"{m.group(1)}:{m.group(2)}"].add(v["id"] if isinstance(v, dict) else v)
def members(tag, seen=()):
    out = set()
    for v in raw.get(tag, ()):
        if v.startswith("#"):
            if v[1:] not in seen: out |= members(v[1:], seen + (tag,))
        else: out.add(v)
    return out
tag_of = defaultdict(set)
for t in raw:
    if t.split(":")[0] in ("c", "minecraft"):
        for b in members(t): tag_of[b].add(t)

# ---- trees per chunk
def provider_mean(p):
    if isinstance(p, (int, float)): return float(p)
    t = p.get("type", "").split(":")[-1]
    if t == "constant": return float(p["value"])
    if t in ("uniform", "biased_to_bottom", "clamped"):
        if "source" in p: return provider_mean(p["source"])
        return (p.get("min_inclusive", 0) + p.get("max_inclusive", 0)) / 2
    if t == "weighted_list":
        d = p["distribution"]; w = sum(e["weight"] for e in d)
        return sum(provider_mean(e["data"]) * e["weight"] for e in d) / max(w, 1)
    if t == "clamped_normal": return float(p.get("mean", 0))
    if t == "trapezoid": return (p.get("min", 0) + p.get("max", 0)) / 2
    return 1.0
def placement_factor(mods):
    f = 1.0
    for m in mods:
        t = m.get("type", "").split(":")[-1]
        if t in ("count", "count_on_every_layer"): f *= provider_mean(m["count"])
        elif t == "rarity_filter": f /= max(m.get("chance", 1), 1)
        elif t == "noise_based_count":   # count = ceil(noise * ratio + offset), noise roughly uniform in [-1, 1]
            r, o = m.get("noise_to_count_ratio", 1), m.get("noise_offset", 0)
            f *= sum(max(0, math.ceil(r * (k / 50 - 1) + o)) for k in range(101)) / 101
        elif t == "noise_threshold_count": f *= (m.get("below_noise", 0) + m.get("above_noise", 0)) / 2
    return f
TREE_TYPES = {"tree", "huge_brown_mushroom", "huge_red_mushroom"}
def configured(ref, depth=0):
    if depth > 6: return None
    if isinstance(ref, dict): return ref
    return load(f"data/{ref.split(':')[0]}/worldgen/configured_feature/{ref.split(':')[1]}.json")
def placed(ref):
    if isinstance(ref, dict): return ref
    if ":" not in ref: ref = "minecraft:" + ref
    return load(f"data/{ref.split(':')[0]}/worldgen/placed_feature/{ref.split(':')[1]}.json")
def tree_share(cf, depth=0):
    """Fraction of placements of this configured feature that grow a standing tree."""
    if cf is None or depth > 6: return 0.0
    t = cf.get("type", "").split(":")[-1]; c = cf.get("config", {})
    if "fallen" in t: return 0.0
    if t in TREE_TYPES or "tree" in t: return 1.0     # vanilla tree, and the mods' own tree feature types
    if t == "random_selector":
        ws = [e.get("chance", 0) for e in c.get("features", [])]
        s = sum(w * share_ref(e["feature"], depth + 1) for w, e in zip(ws, c.get("features", [])))
        return s + max(0.0, 1 - sum(ws)) * share_ref(c.get("default"), depth + 1)
    if t == "simple_random_selector":
        fs = c.get("features", []); fs = fs if isinstance(fs, list) else [fs]
        return sum(share_ref(f, depth + 1) for f in fs) / max(len(fs), 1)
    if t == "random_boolean_selector":
        return (share_ref(c.get("feature_true"), depth + 1) + share_ref(c.get("feature_false"), depth + 1)) / 2
    return 0.0
BUSH = re.compile(r"bush|shrub")
def share_ref(ref, depth):
    """tree_share of a placed-feature reference; bushes (leaf blobs on a log) count a quarter of a tree."""
    w = 0.25 if isinstance(ref, str) and BUSH.search(ref.split(":")[-1]) else 1.0
    return w * tree_share(configured_of_placed(ref), depth)
def configured_of_placed(p):
    pf = placed(p) if not (isinstance(p, dict) and "type" in p) else None
    if isinstance(p, dict) and "type" in p: return p          # inline configured feature
    if pf is None: return None
    return configured(pf["feature"])
def trees_per_chunk(b):
    steps = b.get("features", [])
    n = 0.0
    for step in steps:
        for f in step if isinstance(step, list) else [step]:
            if isinstance(f, str) and ("fallen" in f or "log" in f.split("/")[-1]): continue
            pf = placed(f)
            if not pf: continue
            share = tree_share(configured(pf["feature"]) if not isinstance(pf["feature"], dict) else pf["feature"])
            if isinstance(f, str) and BUSH.search(f.split(":")[-1]): share *= 0.25
            if share: n += share * placement_factor(pf.get("placement", []))
    return round(n, 3)

# ---- landform the biome expects
TOKENS = [("peak", r"peaks?$|spires?$|_mountain$|haze_mountain|crag"), ("cliff", r"cliffs?$|canyon$|chasm$|yosemite_cliffs|basalt_cliffs"),
          ("mesa", r"mesa$|bryce|badlands$"), ("highland", r"highlands?$|plateau$|slopes$|alpine_grove|treeline$")]
def terrain(bid, tags):
    n = bid.split(":")[1]
    if "c:is_mountain/peak" in tags: return "peak"
    for k, rx in TOKENS[:2]:
        if re.search(rx, n): return k
    if "c:is_mountain/slope" in tags or "c:is_mountain" in tags or "minecraft:is_mountain" in tags: return "mountain"
    if re.search(TOKENS[2][1], n): return "mesa"
    if "c:is_plateau" in tags or re.search(TOKENS[3][1], n): return "highland"
    if "c:is_windswept" in tags or "c:is_hill" in tags or "minecraft:is_hill" in tags: return "hill"
    return "flat"

# ---- exclusions: not surface land, fantasy, fixed-colour autumn leaves, or waiting on a mask
NOT_LAND = {"c:is_cave", "c:is_underground", "c:is_aquatic", "c:is_ocean", "c:is_river", "c:is_beach", "c:is_stony_shores",
            "c:is_nether", "c:is_end", "minecraft:is_ocean", "minecraft:is_river", "minecraft:is_beach", "minecraft:is_nether", "minecraft:is_end"}
FANTASY = {"c:is_magical", "c:is_mushroom"}   # c:is_spooky also holds dark_forest, so spooky biomes are listed below
EXCLUDE = set("""biomesoplenty:mystic_grove biomesoplenty:ominous_woods biomesoplenty:auroral_garden biomesoplenty:origin_valley
biomesoplenty:wintry_origin_valley minecraft:pale_garden minecraft:deep_dark minecraft:mushroom_fields minecraft:ice_spikes minecraft:the_void
terralith:alpha_islands terralith:alpha_islands_winter terralith:mirage_isles terralith:moonlight_grove terralith:moonlight_valley
terralith:amethyst_canyon terralith:amethyst_rainforest terralith:warped_mesa terralith:skylands_autumn terralith:skylands_spring
terralith:skylands_summer terralith:skylands_winter terralith:volcanic_crater terralith:volcanic_peaks terralith:caldera terralith:yellowstone
terralith:scarlet_mountains terralith:emerald_peaks terralith:snowy_cherry_grove terralith:desert_oasis terralith:red_oasis
biomesoplenty:maple_woods biomesoplenty:snowy_maple_woods biomesoplenty:seasonal_forest biomesoplenty:pumpkin_patch biomesoplenty:orchard
biomesoplenty:volcano biomesoplenty:volcanic_plains biomesoplenty:hot_springs biomesoplenty:crystalline_chasm biomesoplenty:jade_cliffs
biomesoplenty:wasteland biomesoplenty:wasteland_steppe biomesoplenty:dead_forest biomesoplenty:old_growth_dead_forest biomesoplenty:spider_nest
biomesoplenty:overgrown_greens biomesoplenty:snowblossom_grove biomesoplenty:fungal_jungle biomesoplenty:gravel_beach biomesoplenty:dune_beach
wilderwild:maple_forest wilderwild:oasis wilderwild:warm_river wilderwild:warm_beach wilderwild:birch_jungle wilderwild:sparse_birch_jungle
terrestria:caldera terrestria:volcanic_island terrestria:japanese_maple_forest terrestria:rainbow_rainforest terrestria:oasis terrestria:canyon
terrestria:lush_desert""".split())
# Water and wetland biomes are placed only on the wetland mask (rule 3); the tag says which.
WET = {"c:is_swamp"}
# Biomes themed on one part of the world: they compete only in these realms (g3 realm names).
REALM = {
 "terralith:sakura_grove": "Palearctic Indomalayan", "terralith:sakura_valley": "Palearctic Indomalayan",
 "terralith:snowy_cherry_grove": "Palearctic", "minecraft:cherry_grove": "Palearctic Indomalayan", "terrestria:sakura_forest": "Palearctic",
 "terralith:bryce_canyon": "Nearctic", "terralith:yosemite_cliffs": "Nearctic", "terralith:yosemite_lowlands": "Nearctic",
 "terralith:shield": "Nearctic", "terralith:shield_clearing": "Nearctic", "terralith:snowy_shield": "Nearctic",
 "terralith:siberian_taiga": "Palearctic", "terralith:siberian_grove": "Palearctic",
 "terralith:lavender_forest": "Palearctic", "terralith:lavender_valley": "Palearctic", "biomesoplenty:lavender_field": "Palearctic",
 "biomesoplenty:redwood_forest": "Nearctic", "terrestria:redwood_forest": "Nearctic", "terrestria:lush_redwood_forest": "Nearctic",
 "terrestria:windswept_redwood_forest": "Nearctic",
 "biomesoplenty:bayou": "Nearctic", "terrestria:cypress_swamp": "Nearctic", "wilderwild:cypress_wetlands": "Nearctic Neotropic",
 "terrestria:outback": "Australasian", "minecraft:bamboo_jungle": "Indomalayan Palearctic",
 "biomesoplenty:mediterranean_forest": "Palearctic", "biomesoplenty:moor": "Palearctic", "biomesoplenty:prairie": "Nearctic Neotropic Palearctic",
}

# Biomes themed on one small real place (a species belt, a landmark). Global placement skips them; an ecoregion
# profile in variants/flora can still use them as a parent ("rebase"), so they appear only where a region is written for them.
PROFILE_ONLY = set("""terralith:sakura_grove terralith:sakura_valley minecraft:cherry_grove terrestria:sakura_forest
terralith:bryce_canyon terralith:yosemite_cliffs terralith:yosemite_lowlands terralith:lavender_forest terralith:lavender_valley
biomesoplenty:lavender_field biomesoplenty:redwood_forest terrestria:redwood_forest terrestria:lush_redwood_forest
terrestria:windswept_redwood_forest minecraft:bamboo_jungle""".split())

biomes = {}
for path in files:
    bid = rid(path, "worldgen/biome")
    if not bid or "/" in bid.split(":")[1]: continue
    tags = tag_of.get(bid, set())
    if bid in EXCLUDE or tags & FANTASY or (tags & NOT_LAND and "c:is_swamp" not in tags): continue   # wetland biomes may carry river tags
    b = load(path)
    if b is None: continue
    if bid.startswith("minecraft:") and bid.split(":")[1] in ("ocean", "river", "beach", "snowy_beach", "stony_shore", "frozen_river", "warm_ocean"): continue
    if "ocean" in bid or "river" in bid or "beach" in bid: continue
    trees = trees_per_chunk(b)
    if any(x.startswith("c:is_tree/") for x in tags): trees = max(trees, 1.0)   # tagged as wooded; the estimate missed a custom feature
    t = float(b.get("temperature", 0.5)); frozen = b.get("temperature_modifier") == "frozen"
    biomes[bid] = {
        "temperature": t, "downfall": float(b.get("downfall", 0.5)), "precipitation": bool(b.get("has_precipitation", True)),
        "frozen": frozen, "trees": trees, "terrain": terrain(bid, tags), "wet": bool(tags & WET),
        "realms": REALM.get(bid, "").split() or None, "profile_only": bid in PROFILE_ONLY, "tags": sorted(x for x in tags if x.startswith("c:"))}
json.dump(biomes, open(out, "w"), indent=1, sort_keys=True)
by = defaultdict(int)
for k in biomes: by[k.split(":")[0]] += 1
print(len(biomes), "biomes", dict(by))
