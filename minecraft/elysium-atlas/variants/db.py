"""Loads and checks the plant and ecoregion database (variants/db; schema in db/README.md).

  plants()      {plant id: entry}, every plant with its render evaluated (entry["feature"]) and its kind
                (tree, ref, ground, cactus) for the feature writer
  ecoregions()  {ecoregion id: entry} with layers as {plant id: weight}
  niches(eco)   {plant id: niche} for one ecoregion: the plant's own niche, overridden by the ecoregion's
  surface(eco)  the ecoregion's ground_surface, checked
  clumps(eco)   {plant id: clump} for one ecoregion: the plant's clump (or its form's default), overridden by the ecoregion's
  patches(eco)  {layer: clump}: layers that grow in patches with open ground between
  colours(eco, leaf_blocks)
                grass, foliage and per-leaf-block colours of an ecoregion, all derived from its species:
                  grass    weighted mean of the `colour` of its grasses (form grass, ground layer)
                  foliage  weighted mean of the `leaf` colour of its trees and shrubs
                  leaves   for each leaf block, the weighted mean over the species that grow that block
"""
import ast, glob, json, os, re
import yaml
import render

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "db")
FORMS = {"tree", "shrub", "shrub_ground", "grass", "fern", "herb", "flower", "succulent", "cactus", "cover"}
LAYERS = ("trees", "shrubs", "ground", "flowers", "cactus")
WOODY = ("tree", "shrub")
_ALLOWED = (ast.Expression, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Tuple, ast.List, ast.Dict, ast.keyword,
            ast.UnaryOp, ast.USub)


def evaluate(text, where):
    """A render expression, with only the builders of render.py in scope."""
    tree = ast.parse(text, mode="eval")
    for n in ast.walk(tree):
        if not isinstance(n, _ALLOWED): raise SystemExit(f"{where}: render may only call the builders in render.py ({type(n).__name__})")
        if isinstance(n, ast.Name) and n.id not in render.NAMES: raise SystemExit(f"{where}: unknown name {n.id} in render")
    return eval(compile(tree, where, "eval"), {"__builtins__": {}}, dict(render.NAMES))


def _yaml(path):
    with open(path) as f: return yaml.safe_load(f) or {}


_cache = {}


def colour_names():
    if "colours" not in _cache: _cache["colours"] = _yaml(os.path.join(DB, "colours.yaml"))
    return _cache["colours"]


def hexcolour(v, where):
    if v is None: return None
    v = colour_names().get(v, v)
    if not (isinstance(v, str) and len(v) == 7 and v[0] == "#"): raise SystemExit(f"{where}: {v!r} is neither #rrggbb nor a name in colours.yaml")
    return v


# conifer genera whose species keep their leaves; larch, bald cypress, dawn redwood and ginkgo drop theirs. A plant's
# own `evergreen` overrides (broadleaf evergreens: live oak, laurels).
EVERGREEN_GENERA = {"Abies", "Picea", "Pinus", "Tsuga", "Pseudotsuga", "Juniperus", "Cupressus", "Chamaecyparis", "Thuja",
                    "Platycladus", "Cryptomeria", "Sequoia", "Sequoiadendron", "Taxus", "Cedrus", "Calocedrus", "Callitropsis",
                    "Podocarpus", "Araucaria", "Torreya", "Cunninghamia", "Keteleeria", "Cephalotaxus", "Sciadopitys"}


# pale garden parts belong to the pale garden biome only (Clay, 2026-10-28)
PALE = re.compile(r"minecraft:pale_(oak_\w+|moss\w*|hanging_moss)|pale_moss")
# the mod's tinted ground blocks: a plant using one is coloured per region from its leaf colour, like a leaf block
TINTED_BLOCK = re.compile(r"elysium_atlas:tinted_\w+")
TINT_LAYERS = ("ground", "flowers")


def plants():
    if "plants" in _cache: return _cache["plants"]
    out = {}
    for p in sorted(glob.glob(os.path.join(DB, "plants", "*.yaml"))):
        for pid, e in _yaml(p).items():
            where = f"{os.path.basename(p)}:{pid}"
            if pid in out: raise SystemExit(f"{where}: plant defined twice")
            for k in ("name", "form", "render"):
                if k not in e: raise SystemExit(f"{where}: missing {k}")
            if e["form"] not in FORMS: raise SystemExit(f"{where}: form {e['form']} not one of {sorted(FORMS)}")
            if e["form"] != "cover" and "latin" not in e: raise SystemExit(f"{where}: a species needs latin")
            if e["form"] in WOODY and "leaf" not in e: raise SystemExit(f"{where}: trees and shrubs need a leaf colour")
            if e["form"] == "grass" and "colour" not in e: raise SystemExit(f"{where}: grasses need a colour")
            e = dict(e, id=pid, file=os.path.basename(p))
            e["leaf"] = hexcolour(e.get("leaf"), where); e["colour"] = hexcolour(e.get("colour"), where)
            e["autumn"] = hexcolour(e.get("autumn"), where)
            if "evergreen" in e and not isinstance(e["evergreen"], bool): raise SystemExit(f"{where}: evergreen is true or false")
            e["evergreen"] = e.get("evergreen", e.get("latin", "").split(" ")[0] in EVERGREEN_GENERA)
            f = evaluate(e["render"], where)
            pale = PALE.search(json.dumps(f) if isinstance(f, dict) else str(f))
            if pale: raise SystemExit(f"{where}: {pale.group(0)} is a pale garden block; real regions use real trees' parts")
            if TINTED_BLOCK.search(e["render"]) and not e["leaf"]: raise SystemExit(f"{where}: a tinted ground block needs a leaf colour")
            if isinstance(f, render.Ref): e["kind"], e["feature"] = "ref", str(f)
            elif f.get("type") == "minecraft:tree": e["kind"], e["feature"] = "tree", f
            elif f.get("type") == "minecraft:block_column": e["kind"], e["feature"] = "cactus", f
            else: e["kind"], e["feature"] = "ground", f
            if e["kind"] in ("tree", "ref") and "sapling" not in e: raise SystemExit(f"{where}: trees need a sapling (survival check)")
            if "sapling" in e: e["sapling"] = render._id(e["sapling"])
            if e.get("niche"): _check_niche(e["niche"], where)
            if e.get("clump"): _check_clump(e["clump"], where)
            out[pid] = e
    _cache["plants"] = out
    return out


def ecoregions():
    if "ecoregions" in _cache: return _cache["ecoregions"]
    P = plants(); out = {}
    for p in sorted(glob.glob(os.path.join(DB, "ecoregions", "*.yaml"))):
        for eid, e in _yaml(p).items():
            where = f"{os.path.basename(p)}:{eid}"
            if not isinstance(eid, int): raise SystemExit(f"{where}: keys are RESOLVE ECO_ID numbers")
            if eid in out: raise SystemExit(f"{where}: ecoregion defined twice")
            for L in LAYERS:
                for pid in (e.get(L) or {}):
                    if pid not in P: raise SystemExit(f"{where}: {L}: unknown plant {pid}")
                    form = P[pid]["form"]
                    if L in ("trees", "shrubs") and P[pid]["kind"] not in ("tree", "ref"):
                        raise SystemExit(f"{where}: {L}: {pid} is not a tree feature")
            if not any(P[p]["form"] == "grass" for p in (e.get("ground") or {})):
                raise SystemExit(f"{where}: name at least one grass in ground (it sets the grass colour)")
            for pid in (e.get("niches") or {}):
                if not any(pid in (e.get(L) or {}) for L in LAYERS): raise SystemExit(f"{where}: niches: {pid} is not listed in a layer")
            for pid, c in (e.get("clumps") or {}).items():
                if not any(pid in (e.get(L) or {}) for L in LAYERS): raise SystemExit(f"{where}: clumps: {pid} is not listed in a layer")
                if c != "none": _check_clump(c, f"{where}: clumps: {pid}")
            for L, c in (e.get("patches") or {}).items():
                if L not in LAYERS or L == "cactus" or not e.get(L): raise SystemExit(f"{where}: patches: {L} is not a layer of this ecoregion")
                _check_clump(c, f"{where}: patches: {L}")
            out[eid] = dict(e, file=os.path.basename(p))
    _cache["ecoregions"] = out
    return out


NICHE_WATER = {"riparian", "wet", "dry", "any"}     # "any" in an ecoregion lifts a species' own niche there
NICHE_SLOPE = {"flat", "steep", "any"}
AMOUNTS = {"none": 0.0, "few": 0.05, "some": 0.12, "many": 0.25}     # share of gentle ground (surface patches); steep ground adds rock


def _check_niche(n, where):
    if not isinstance(n, dict) or set(n) - {"elevation", "water", "slope"}: raise SystemExit(f"{where}: niche keys are elevation, water, slope")
    if "elevation" in n and not (isinstance(n["elevation"], list) and len(n["elevation"]) == 2 and n["elevation"][0] < n["elevation"][1]):
        raise SystemExit(f"{where}: elevation is [low, high] metres")
    if n.get("water", "riparian") not in NICHE_WATER: raise SystemExit(f"{where}: water is one of {sorted(NICHE_WATER)}")
    if n.get("slope", "flat") not in NICHE_SLOPE: raise SystemExit(f"{where}: slope is one of {sorted(NICHE_SLOPE)}")
    return n


def niches(eco):
    P = plants(); out = {}
    for L in LAYERS:
        for p in (eco.get(L) or {}):
            n = dict(P[p].get("niche") or {})
            n.update((eco.get("niches") or {}).get(p) or {})
            _check_niche(n, f"{eco['name']}: {p}")
            n = {k: v for k, v in n.items() if v != "any"}
            if n: out[p] = n
    return out


FORM_CLUMP = {"flower": {"size": 12, "share": 0.35}}    # single-species drifts unless a plant or ecoregion says otherwise


def _check_clump(c, where):
    if not isinstance(c, dict) or set(c) - {"size", "share", "outside"} or not {"size", "share"} <= set(c):
        raise SystemExit(f"{where}: clump is {{size: blocks, share: 0-1, outside: 0-1 (optional)}} or none")
    if not (2 <= c["size"] <= 256 and 0 < c["share"] < 1 and 0 <= c.get("outside", 0.1) <= 1):
        raise SystemExit(f"{where}: clump size 2-256 blocks, share and outside between 0 and 1")
    return c


def clumps(eco):
    P = plants(); out = {}
    for L in LAYERS:
        if L == "cactus": continue
        for p in (eco.get(L) or {}):
            c = (eco.get("clumps") or {}).get(p, P[p].get("clump") or FORM_CLUMP.get(P[p]["form"]))
            if c and c != "none": out[p] = {"outside": 0.1, **c}
    return out


def patches(eco):
    return {L: {"outside": 0.1, **c} for L, c in (eco.get("patches") or {}).items()}


def surface(eco):
    """ground_surface: {geology: text, rock: [blocks], outcrops: amount, soil: {block: amount}, top: block, subsoil: block}."""
    g = eco.get("ground_surface")
    if not g: return None
    where = f"{eco['name']}: ground_surface"
    if set(g) - {"geology", "rock", "outcrops", "outcrop_size", "soil", "top", "subsoil", "strata", "ledges", "banks"}:
        raise SystemExit(f"{where}: unknown key")
    if g.get("outcrops", "none") not in AMOUNTS: raise SystemExit(f"{where}: outcrops is one of {list(AMOUNTS)}")
    if g.get("outcrop_size", "large") not in ("large", "small"): raise SystemExit(f"{where}: outcrop_size is large or small")
    ledges = g.get("ledges")
    if ledges and (set(ledges) - {"every", "keep"} or not 1 <= ledges.get("every", 3) <= 16 or not 0 < ledges.get("keep", 1) <= 1):
        raise SystemExit(f"{where}: ledges is {{every: 1-16, keep: 0-1}}")
    banks = g.get("banks")
    if banks and (set(banks) - {"blocks", "distance"} or not banks.get("blocks")): raise SystemExit(f"{where}: banks is {{blocks: [..], distance: n}}")
    for b, a in (g.get("soil") or {}).items():
        if a not in AMOUNTS: raise SystemExit(f"{where}: soil {b}: amount is one of {list(AMOUNTS)}")
    return {"geology": g.get("geology", ""), "rock": [render._id(b) for b in (g.get("rock") or [])],
            "outcrops": AMOUNTS[g.get("outcrops", "none")],
            "soil": {render._id(b): AMOUNTS[a] for b, a in (g.get("soil") or {}).items()},
            "top": render._id(g["top"]) if g.get("top") else None,
            "subsoil": render._id(g["subsoil"]) if g.get("subsoil") else None,
            "small_outcrops": g.get("outcrop_size") == "small",
            "strata": [render._id(b) for b in (g.get("strata") or [])],
            "ledges": {"every": ledges.get("every", 3), "keep": ledges.get("keep", 1.0)} if ledges else None,
            "banks": {"blocks": [render._id(b) for b in banks["blocks"]], "distance": banks.get("distance", 2)} if banks else None}


def _mean(pairs):
    pairs = [(c, w) for c, w in pairs if c and w > 0]
    if not pairs: return None
    tw = sum(w for _, w in pairs)
    rgb = [sum(int(c[1 + 2 * i:3 + 2 * i], 16) * w for c, w in pairs) / tw for i in range(3)]
    return "#%02x%02x%02x" % tuple(round(v) for v in rgb)


def colours(eco, leaf_blocks):
    """(grass, foliage, {leaf block: colour}) for one ecoregion entry. leaf_blocks(plant id) -> set of leaf blocks."""
    P = plants()
    grass = _mean([(P[p]["colour"], w) for p, w in (eco.get("ground") or {}).items() if P[p]["form"] == "grass"])
    woody = [(p, w) for L in ("trees", "shrubs") for p, w in (eco.get(L) or {}).items() if P[p].get("leaf")]
    foliage = _mean([(P[p]["leaf"], w) for p, w in woody]) or grass     # treeless (tundra): foliage follows the turf
    per = {}
    tinted = [(p, w) for L in TINT_LAYERS for p, w in (eco.get(L) or {}).items() if P[p].get("leaf")]
    for p, w in woody + tinted:
        for b in leaf_blocks(p): per.setdefault(b, []).append((P[p]["leaf"], w))
    return grass, foliage, {b: _mean(v) for b, v in per.items()}


def evergreen_blocks(eco, leaf_blocks):
    """Leaf blocks on which every woody species of the ecoregion is evergreen: they keep the summer colour all year."""
    P = plants(); per = {}
    for L in ("trees", "shrubs") + TINT_LAYERS:
        for p, w in (eco.get(L) or {}).items():
            if w <= 0 or not P[p].get("leaf"): continue
            for b in leaf_blocks(p): per.setdefault(b, []).append(P[p]["evergreen"])
    return {b for b, v in per.items() if all(v)}


def coast_types():
    """{type: {"low": blocks or None, "bands": [(width, {block id: weight})]}} from coast_types.yaml."""
    if "coast_types" in _cache: return _cache["coast_types"]
    out = {}
    for t, e in _yaml(os.path.join(DB, "coast_types.yaml")).items():
        if set(e) - {"low", "bands"}: raise SystemExit(f"coast_types.yaml:{t}: keys are low, bands")
        bands = []
        for w, mix in e["bands"]:
            if w <= 0 or not mix: raise SystemExit(f"coast_types.yaml:{t}: a band is [width > 0, {{block: weight}}]")
            bands.append((w, {("grass" if b == "grass" else render._id(b)): float(x) for b, x in mix.items()}))
        out[t] = {"low": e.get("low"), "bands": bands}
    _cache["coast_types"] = out
    return out


def coasts():
    """{ecoregion id: {"coast": {type: share}, "sea": {...}}} from coasts.yaml (hand-authored coastal pass)."""
    if "coasts" in _cache: return _cache["coasts"]
    T = coast_types(); out = {}
    for group, regions in _yaml(os.path.join(DB, "coasts.yaml")).items():
        for eid, e in regions.items():
            where = f"coasts.yaml:{group}:{eid}"
            for t, sh in e["coast"].items():
                if t not in T: raise SystemExit(f"{where}: unknown coast type {t}")
            if abs(sum(e["coast"].values()) - 1) > 0.02: raise SystemExit(f"{where}: coast shares must add up to 1")
            out[int(eid)] = e
    _cache["coasts"] = out
    return out
