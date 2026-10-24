"""Loads and checks the plant and ecoregion database (variants/db; schema in db/README.md).

  plants()      {plant id: entry}, every plant with its render evaluated (entry["feature"]) and its kind
                (tree, ref, ground, cactus) for the feature writer
  ecoregions()  {ecoregion id: entry} with layers as {plant id: weight}
  colours(eco, leaf_blocks)
                grass, foliage and per-leaf-block colours of an ecoregion, all derived from its species:
                  grass    weighted mean of the `colour` of its grasses (form grass, ground layer)
                  foliage  weighted mean of the `leaf` colour of its trees and shrubs
                  leaves   for each leaf block, the weighted mean over the species that grow that block
"""
import ast, glob, os
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
            f = evaluate(e["render"], where)
            if isinstance(f, render.Ref): e["kind"], e["feature"] = "ref", str(f)
            elif f.get("type") == "minecraft:tree": e["kind"], e["feature"] = "tree", f
            elif f.get("type") == "minecraft:block_column": e["kind"], e["feature"] = "cactus", f
            else: e["kind"], e["feature"] = "ground", f
            if e["kind"] in ("tree", "ref") and "sapling" not in e: raise SystemExit(f"{where}: trees need a sapling (survival check)")
            if "sapling" in e: e["sapling"] = render._id(e["sapling"])
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
            out[eid] = dict(e, file=os.path.basename(p))
    _cache["ecoregions"] = out
    return out


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
    foliage = _mean([(P[p]["leaf"], w) for p, w in woody])
    per = {}
    for p, w in woody:
        for b in leaf_blocks(p): per.setdefault(b, []).append((P[p]["leaf"], w))
    return grass, foliage, {b: _mean(v) for b, v in per.items()}
