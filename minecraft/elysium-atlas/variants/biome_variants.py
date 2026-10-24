"""Regional biome variants: definitions and generator.

A variant is a child of a parent biome in one or more region units (regions.py: one per ecoregion). It inherits
everything from its parent at runtime (tags, spawns, carvers, features after every mod's changes, surface rules,
key and list checks; see Variants.java). It declares only what differs: colours and effects, attributes, and a
feature patch. Temperature, downfall and precipitation are always the atlas biome's, so seasons and snow behave
the same.

Two sources, in order of precedence for a (unit, atlas biome) pair:
  VARIANTS below       hand-written variants
  flora/*.py FLORA     per-ecoregion profiles: hand-picked colours, and the parent's plants replaced by the
                       ecoregion's plant list. Ecoregions without a profile keep the atlas biome unchanged.
Data: data/unit_biomes.json and data/ecoregions.json (bake/bake_regions.py).

  python3 variants/biome_variants.py SERVER_JAR TERRALITH_JAR      # writes src/main/resources/...
  python3 variants/biome_variants.py SERVER_JAR TERRALITH_JAR --check

Feature patch: "remove" names placed features of the parent; "add" names placed features (existing ones are
copied under elysium:variant/<namespace>/<path>), appended to the step so feature order stays acyclic.
"""
import colorsys, glob, importlib.util, json, math, os, re, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "src", "main", "resources")
sys.path.insert(0, HERE)
from regions import REGIONS, unit_names
from plants import PLANTS

FOREST_ATTRS = "minecraft:forest"   # plain overworld sky, fog and music, for variants of stylized parents
CLIMATE = ("temperature", "downfall", "has_precipitation", "temperature_modifier")
MIN_SHARE = 0.003                   # atlas biome share of a unit that gets a variant
MIN_CELLS = 12
TREES_PER_CHUNK_AT_FULL_COVER = 12.0
# default tree and shrub cover by WWF habitat type (Ecoregions 2017 BIOME_NUM), when a profile gives none
TREE_COVER = {1: 0.8, 2: 0.5, 3: 0.6, 4: 0.6, 5: 0.6, 6: 0.5, 7: 0.25, 8: 0.15, 9: 0.15, 10: 0.15, 11: 0.03, 12: 0.35, 13: 0.05, 14: 0.6}
SHRUB_COVER = {7: 0.1, 8: 0.05, 10: 0.1, 12: 0.3, 13: 0.15}
GENERATED_DIRS = ("data/elysium/worldgen/biome/eco", "data/elysium/worldgen/placed_feature/flora",
                  "data/elysium/worldgen/configured_feature/flora", "data/elysium/worldgen/configured_feature/plant")

VARIANTS = {}     # hand-written variants; the European set moved to flora/europe.py (slice-9)


def load_flora():
    out = {}
    for p in sorted(glob.glob(os.path.join(HERE, "flora", "*.py"))):
        spec = importlib.util.spec_from_file_location("flora_" + os.path.basename(p)[:-3], p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        for k, v in m.FLORA.items():
            if k in out: raise SystemExit(f"ecoregion {k} has two flora profiles")
            for layer in ("trees", "shrubs", "ground", "flowers", "cactus"):
                for plant in v.get(layer, {}):
                    if plant not in PLANTS: raise SystemExit(f"flora {k}: unknown plant {plant}")
            out[k] = v
    return out


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


# ---------------------------------------------------------------- parent plants
PLANT_BLOCKS = {f"minecraft:{b}" for b in (
    "short_grass tall_grass fern large_fern dandelion poppy blue_orchid allium azure_bluet red_tulip orange_tulip white_tulip "
    "pink_tulip oxeye_daisy cornflower lily_of_the_valley sunflower lilac rose_bush peony torchflower pink_petals wildflowers "
    "leaf_litter bush firefly_bush short_dry_grass tall_dry_grass dead_bush cactus cactus_flower bamboo pitcher_plant "
    "open_eyeblossom closed_eyeblossom").split()}


# the flora mods' plant blocks, by name: their flowers, grasses, bushes and the like
MOD_PLANT = re.compile(r"^(biomesoplenty|wilderwild|terrestria):.*(grass|flower|bloom|bush|fern|petal|lily|rose|tulip|daisy|clover|sprout|"
                       r"lavender|goldenrod|oats|cattail|reed|weed|thistle|pear|cactus|agave|yucca|paintbrush|marigold|phlox|lantana|datura|"
                       r"tumbleweed|shrub|bramble|sprout|dune|moss|seed|lupine|aster|violet|poppy|iris|orchid|hydrangea|wildflower)")


class Plants:
    """Which of a parent's placed features are plants, and how many trees per chunk they make."""
    def __init__(self, src): self.src = src; self.memo = {}

    def _walk(self, node, seen):
        """(is_plant, has_tree) for a configured feature JSON fragment."""
        plant = tree = False
        if isinstance(node, dict):
            t = node.get("type")
            if t in ("minecraft:tree", "minecraft:fallen_tree", "minecraft:bamboo"): plant = True; tree = t == "minecraft:tree"
            elif isinstance(t, str) and "tree" in t:                     # the mods' own tree feature types
                plant = True; tree = "fallen" not in t
            n = node.get("Name")
            if n in PLANT_BLOCKS or (isinstance(n, str) and MOD_PLANT.match(n)): plant = True
            for k, v in node.items():
                if k == "feature" and isinstance(v, str):
                    p, tr = self.placed_ref(v, seen); plant |= p; tree |= tr
                else:
                    p, tr = self._walk(v, seen); plant |= p; tree |= tr
        elif isinstance(node, list):
            for v in node: p, tr = self._walk(v, seen); plant |= p; tree |= tr
        return plant, tree

    def placed_ref(self, ident, seen):
        """A "feature" string inside a configured feature names a placed feature; inside a placed one a configured."""
        if ident in seen: return False, False
        seen = seen | {ident}
        for kind in ("placed_feature", "configured_feature"):
            try: j = self.src.get(kind, ident)
            except SystemExit: continue
            if kind == "placed_feature":
                return self.configured(j["feature"], seen) if isinstance(j["feature"], str) else self._walk(j["feature"], seen)
            return self._walk(j, seen)
        return False, False

    def configured(self, ident, seen=frozenset()):
        if ident in self.memo: return self.memo[ident]
        try: r = self._walk(self.src.get("configured_feature", ident), seen | {ident})
        except SystemExit: r = (False, False)
        self.memo[ident] = r; return r

    def placed(self, ident):
        j = self.src.get("placed_feature", ident); f = j["feature"]
        plant, tree = self.configured(f) if isinstance(f, str) else self._walk(f, frozenset())
        return plant, tree, expected_count(j["placement"]) if tree else 0.0

    def of_biome(self, biome_json):
        """(plant feature ids in the parent, expected trees per chunk)."""
        ids, trees = [], 0.0
        for step in biome_json.get("features", []):
            for f in step:
                p, _, n = self.placed(f)
                if p: ids.append(f); trees += n
        return ids, trees


def _dist_mean(d):
    if isinstance(d, (int, float)): return float(d)
    t = d.get("type")
    if t == "minecraft:constant": return float(d["value"])
    if t == "minecraft:uniform": return (d["min_inclusive"] + d["max_inclusive"]) / 2
    if t == "minecraft:weighted_list":
        w = sum(e["weight"] for e in d["distribution"]); return sum(_dist_mean(e["data"]) * e["weight"] for e in d["distribution"]) / w
    if t in ("minecraft:clamped", "minecraft:clamped_normal"): return _dist_mean(d.get("source", d.get("mean", 1)))
    if t in ("minecraft:biased_to_bottom", "minecraft:very_biased_to_bottom"): return (d["min_inclusive"] + d["max_inclusive"]) / 3
    return 1.0


def expected_count(placement):
    n = 1.0
    for m in placement:
        t = m["type"]
        if t == "minecraft:count": n *= _dist_mean(m["count"])
        elif t == "minecraft:rarity_filter": n /= m["chance"]
        elif t == "minecraft:noise_threshold_count": n *= (m["above_noise"] + m["below_noise"]) / 2
        elif t == "minecraft:noise_based_count": n *= m["noise_to_count_ratio"] / 2
        elif t == "minecraft:count_on_every_layer": n *= _dist_mean(m["count"])
    return max(0.0, n)


# ---------------------------------------------------------------- colours
def rgb(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
def hexc(c): return "#%02x%02x%02x" % c


def shade(c, f):
    h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in c]); return tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(h, s, max(0, min(1, v * f))))


# ---------------------------------------------------------------- flora features
LEVELS = [0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 15]


def level(x): return min(range(len(LEVELS)), key=lambda i: abs(LEVELS[i] - x))


def count_of(n):
    """A count distribution with mean n."""
    lo = int(math.floor(n)); f = n - lo
    if f < 0.01: return lo
    return {"type": "minecraft:weighted_list", "distribution": [{"data": lo, "weight": int(round((1 - f) * 100))}, {"data": lo + 1, "weight": int(round(f * 100))}]}


def survive(sapling): return {"type": "minecraft:block_predicate_filter", "predicate": {"type": "minecraft:would_survive", "state": {"Name": sapling, **({"Properties": {"stage": "0"}} if "sapling" in sapling else {})}}}


def selector(weighted):
    """random_selector with the given (placed feature json, weight) pairs, weights honoured."""
    items = [(f, w) for f, w in weighted if w > 0]
    feats = []; rest = sum(w for _, w in items)
    for f, w in items[:-1]:
        feats.append({"chance": round(w / rest, 6), "feature": f}); rest -= w
    return {"type": "minecraft:random_selector", "config": {"default": items[-1][0], "features": feats}}


def scatter(count, tries, spread, heightmap="MOTION_BLOCKING", extra=None):
    p = [{"type": "minecraft:count", "count": count_of(count)}] if count != 1 else []
    return p + [{"type": "minecraft:in_square"}, {"type": "minecraft:heightmap", "heightmap": heightmap}, {"type": "minecraft:biome"},
                {"type": "minecraft:count", "count": tries},
                {"type": "minecraft:random_offset", "xz_spread": {"type": "minecraft:trapezoid", "min": -spread, "max": spread, "plateau": 0},
                 "y_spread": {"type": "minecraft:trapezoid", "min": -3, "max": 3, "plateau": 0}},
                {"type": "minecraft:block_predicate_filter", "predicate": extra or {"type": "minecraft:matching_block_tag", "tag": "minecraft:air"}}]


class Flora:
    """Writes the configured and placed features of ecoregion plant lists."""
    def __init__(self): self.files = {}; self.plant_ids = {}

    def plant(self, name):
        kind, feat, sapling, _ = PLANTS[name]
        if kind == "ref": return feat, sapling
        cid = f"elysium:plant/{name}"
        self.files[f"data/elysium/worldgen/configured_feature/plant/{name}.json"] = feat
        return cid, sapling

    def trees(self, eco, layer, plants, n):
        key = f"flora/{eco}/{layer}_{level(n)}"
        if f"data/elysium/worldgen/placed_feature/{key}.json" not in self.files:
            items = []
            for p, w in plants.items():
                cid, sap = self.plant(p)
                items.append(({"feature": cid, "placement": [survive(sap)]}, w))
            self.files[f"data/elysium/worldgen/configured_feature/flora/{eco}/{layer}.json"] = selector(items)
            self.files[f"data/elysium/worldgen/placed_feature/{key}.json"] = {"feature": f"elysium:flora/{eco}/{layer}", "placement": [
                {"type": "minecraft:count", "count": count_of(LEVELS[level(n)])}, {"type": "minecraft:in_square"},
                {"type": "minecraft:surface_water_depth_filter", "max_water_depth": 0},
                {"type": "minecraft:heightmap", "heightmap": "OCEAN_FLOOR"}, {"type": "minecraft:biome"}]}
        return f"elysium:{key}"

    def blocks(self, eco, layer, plants, n, tries, spread):
        key = f"flora/{eco}/{layer}_{level(n)}"
        if f"data/elysium/worldgen/placed_feature/{key}.json" not in self.files:
            entries = {}
            for p, w in plants.items():
                es = PLANTS[p][1]["config"]["to_place"]["entries"]; tot = sum(e["weight"] for e in es)
                for e in es:
                    k = json.dumps(e["data"], sort_keys=True); entries[k] = entries.get(k, 0) + w * e["weight"] / tot
            scale = 1000 / max(entries.values())
            self.files[f"data/elysium/worldgen/configured_feature/flora/{eco}/{layer}.json"] = {"type": "minecraft:simple_block", "config": {"to_place": {
                "type": "minecraft:weighted_state_provider", "entries": [{"data": json.loads(k), "weight": max(1, int(round(w * scale)))} for k, w in entries.items()]}}}
            self.files[f"data/elysium/worldgen/placed_feature/{key}.json"] = {"feature": f"elysium:flora/{eco}/{layer}",
                                                                               "placement": scatter(LEVELS[level(n)], tries, spread)}
        return f"elysium:{key}"

    def cactus(self, eco, plants, n):
        key = f"flora/{eco}/cactus_{level(n)}"
        if f"data/elysium/worldgen/placed_feature/{key}.json" not in self.files:
            items = [({"feature": self.plant_inline(p), "placement": [{"type": "minecraft:block_predicate_filter", "predicate": {
                "type": "minecraft:would_survive", "state": base_state(p)}}]}, w) for p, w in plants.items()]
            self.files[f"data/elysium/worldgen/configured_feature/flora/{eco}/cactus.json"] = selector(items)
            self.files[f"data/elysium/worldgen/placed_feature/{key}.json"] = {"feature": f"elysium:flora/{eco}/cactus",
                "placement": scatter(LEVELS[level(n)], 6, 7, extra={"type": "minecraft:matching_block_tag", "tag": "minecraft:air"})}
        return f"elysium:{key}"

    def plant_inline(self, name):
        cid = f"elysium:plant/{name}"; self.files[f"data/elysium/worldgen/configured_feature/plant/{name}.json"] = PLANTS[name][1]; return cid


def base_state(name):
    """The block a cactus-layer plant puts on the ground, for its survival check."""
    kind, feat = PLANTS[name][:2]
    if kind == "cactus": return {"Name": "minecraft:cactus", "Properties": {"age": "0"}}
    return feat["config"]["to_place"]["entries"][0]["data"]


# ---------------------------------------------------------------- generation
def title(ident):
    return " ".join(w.capitalize() for w in ident.split(":")[1].replace("/", " ").split("_"))


def generate(src, check=False):
    flora_db = load_flora()
    data = os.path.join(HERE, "data")
    unit_biomes = json.load(open(os.path.join(data, "unit_biomes.json")))
    ecos = json.load(open(os.path.join(data, "ecoregions.json")))
    plants = Plants(src); flora = Flora(); biome_cache = {}

    def biome(ident):
        if ident not in biome_cache: biome_cache[ident] = src.get("biome", ident)
        return biome_cache[ident]

    out = {}; placed = {}; lang = {}; table = {}; claims = {}

    def claim(vid, unit, atlas_biome):
        k = (unit, atlas_biome)
        if k in claims: raise SystemExit(f"{vid} and {claims[k]} both replace {atlas_biome} in {unit}")
        claims[k] = vid

    # ---- hand-written
    for name, v in VARIANTS.items():
        vid = f"elysium:{name}"; parent = biome(v["parent"])
        units = [u for r in v["regions"] for u in unit_names(r)]
        for u in units:
            for a in v.get("replaces", [v["parent"]]): claim(vid, u, a)
        present = {f for s in parent["features"] for f in s}
        for f in v.get("remove", []):
            if f not in present: raise SystemExit(f"{vid}: parent {v['parent']} has no feature {f} to remove")
        b = dict(parent)
        b["effects"] = {**parent.get("effects", {}), **v.get("effects", {})}
        if b["effects"].get("grass_color_modifier") == "none": del b["effects"]["grass_color_modifier"]
        if "attributes_from" in v: b["attributes"] = biome(v["attributes_from"]).get("attributes", {})
        out[f"data/elysium/worldgen/biome/{name}.json"] = b
        add = {}
        for step, ids in v.get("add", {}).items():
            add[step] = []
            for f in ids:
                placed[f"data/elysium/worldgen/placed_feature/variant/{f.split(':')[0]}/{f.split(':')[1]}.json"] = src.get("placed_feature", f)
                add[step].append(wrapped(f))
        table[vid] = {"parent": v["parent"], "regions": units, "add_features": add, "remove_features": v.get("remove", []), "why": v["why"]}
        if "replaces" in v: table[vid]["replaces"] = v["replaces"]
        lang[f"biome.elysium.{name}"] = v["name"]

    # ---- generated
    n_flora = 0
    for unit, counts in unit_biomes.items():
        eid = unit.split(":")[1]; prof = flora_db.get(int(eid))
        if not prof: continue
        total = sum(counts.values()); habitat = ecos.get(eid, {}).get("biome_num", 4)
        grass, foliage = rgb(prof["grass"]), rgb(prof["foliage"])
        pick = [(a, n) for a, n in counts.items() if (unit, a) not in claims and "ocean" not in a and n >= MIN_CELLS and n / total >= MIN_SHARE]
        if not pick: continue
        # plant list: tree counts follow the profile's cover, varied between atlas biomes by their own tree counts
        rebase = prof.get("rebase", {})
        tcount = {a: plants.of_biome(biome(a))[1] for a, _ in pick}
        tmean = sum(tcount[a] * n for a, n in pick) / sum(n for _, n in pick)
        tree_cover = prof.get("tree_cover", TREE_COVER.get(habitat, 0.3))
        shrub_cover = prof.get("shrub_cover", SHRUB_COVER.get(habitat, 0.03))
        open_cover = max(0.0, 1.0 - tree_cover)
        main = max(pick, key=lambda an: an[1])[0]
        for a, n in pick:
            base_id = rebase.get(a, a); base = biome(base_id); atlas = biome(a)
            m = max(0.25, min(1.6, ((tcount[a] + 0.5) / (tmean + 0.5)) ** 0.5))
            vid = f"elysium:eco/{eid}/{base_id.split(':')[1] if base_id.startswith('minecraft:') else base_id.replace(':', '_')}"
            if a != base_id: vid += f"_from_{a.split(':')[1]}"
            claim(vid, unit, a)
            remove, _ = plants.of_biome(base)
            add = []
            if prof.get("trees"):
                add.append(flora.trees(eid, "trees", prof["trees"], TREES_PER_CHUNK_AT_FULL_COVER * tree_cover * m * prof.get("tree_density", 1.0)))
            if prof.get("shrubs"):
                add.append(flora.trees(eid, "shrubs", prof["shrubs"], (1.0 + 12 * shrub_cover) * prof.get("shrub_density", 1.0) * min(1.5, m ** 0.5)))
            if prof.get("ground"):
                add.append(flora.blocks(eid, "ground", prof["ground"], (1 + 6 * open_cover) * max(0.5, min(1.5, 1.5 - 0.5 * m)), 32, 7))
            if prof.get("flowers"):
                add.append(flora.blocks(eid, "flowers", prof["flowers"], prof.get("flower_density", 1.0), 24, 6))
            if prof.get("cactus"):
                add.append(flora.cactus(eid, prof["cactus"], prof.get("cactus_density", 0.5)))
            b = dict(base)
            for k in CLIMATE:
                if k in atlas: b[k] = atlas[k]
                else: b.pop(k, None)
            eff = dict(base.get("effects", {}))
            eff["grass_color"] = hexc(shade(grass, 1.0 - 0.06 * (m - 1))); eff["foliage_color"] = hexc(foliage)
            if eff.get("grass_color_modifier") == "swamp" and a != base_id: eff.pop("grass_color_modifier")
            b["effects"] = eff
            path = vid.split(":")[1]
            out[f"data/elysium/worldgen/biome/{path}.json"] = b
            table[vid] = {"parent": base_id, "regions": [unit], "add_features": {"vegetal_decoration": add}, "remove_features": remove,
                          "why": prof["why"]}
            if a != base_id: table[vid]["replaces"] = [a]
            lang[f"biome.elysium.{path.replace('/', '.')}"] = prof["name"] if a == main else f"{prof['name']} ({title(a)})"
            n_flora += 1
    files = {**out, **placed, **flora.files,
             "assets/elysium/lang/en_us.json": lang,
             "elysium_atlas/variants.json": {"format": 2, "generated_by": "variants/biome_variants.py", "variants": table}}
    if check:
        stale = [p for p, d in files.items() if not os.path.exists(os.path.join(RES, p)) or json.load(open(os.path.join(RES, p))) != d]
        extra = [p for g in GENERATED_DIRS for p in glob.glob(os.path.join(RES, g, "**", "*.json"), recursive=True)
                 if os.path.relpath(p, RES) not in files]
        print("stale:" if stale or extra else "up to date", *stale[:20], *extra[:20]); return not stale and not extra
    for g in GENERATED_DIRS: shutil.rmtree(os.path.join(RES, g), ignore_errors=True)
    for p, d in files.items():
        f = os.path.join(RES, p); os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh: json.dump(d, fh, indent=1 if p.endswith("variants.json") or "lang" in p else None, separators=None if "lang" in p or p.endswith("variants.json") else (",", ":")); fh.write("\n")
    print(f"{len(VARIANTS)} hand-written, {n_flora} from {len(flora_db)} ecoregion profiles; "
          f"{len(table)} variants, {len(placed) + len(flora.files)} feature files")
    return True


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    ok = generate(Sources(*a), check="--check" in sys.argv)
    sys.exit(0 if ok else 1)
