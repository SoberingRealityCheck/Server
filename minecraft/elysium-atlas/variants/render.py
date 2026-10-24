"""Feature builders for the plant database (db/plants/*.yaml, field `render`).

A render is one call of a function below, written as text in the database and evaluated by db.py with only
these names available. Block and feature ids without a namespace are minecraft:.
  tree(log, leaves, trunk, foliage, size=None, decorators=(), vines=True)   a configured tree
    trunks:  straight(base, a, b), forking(base, a, b), fancy(base, a, b)
    crowns:  blob(r, h, off), bushf(r, h, off), acaciaf(r, off), pinef(r, h, off), sprucef(r, off, trunk_h), fancyf(r, h, off)
    U(a, b) a uniform integer; FANCY_SIZE the size rule fancy trees need; moss(...) hanging pale moss
  ref(feature)                         an existing configured feature (vanilla or a flora mod)
  flowers(block, ..., weights=[...])   single blocks; (block, {properties}) for blocks with properties
  segmented(block, property)           leaf litter, wildflowers and other segmented ground blocks
  column(block, lo, hi, cap, chance)   a cactus-like column
"""


def _id(s): return s if ":" in s else "minecraft:" + s


DIRT = {"type": "minecraft:rule_based_state_provider", "rules": [{"if_true": {"type": "minecraft:not", "predicate": {
    "type": "minecraft:matching_block_tag", "tag": "minecraft:cannot_replace_below_tree_trunk"}},
    "then": {"type": "minecraft:simple_state_provider", "state": {"Name": "minecraft:dirt"}}}]}


def _state(name, **props): return {"type": "minecraft:simple_state_provider", "state": {"Name": name, **({"Properties": props} if props else {})}}
def _log(b): return _state(_id(b), axis="y")
def _leaves(b): return _state(_id(b), distance="7", persistent="false", waterlogged="false")
def U(a, b): return {"type": "minecraft:uniform", "min_inclusive": a, "max_inclusive": b}


def tree(log, leaves, trunk, foliage, size=None, decorators=(), vines=True):
    return {"type": "minecraft:tree", "config": {
        "below_trunk_provider": DIRT, "decorators": list(decorators), "foliage_placer": foliage,
        "foliage_provider": _leaves(leaves), "ignore_vines": vines,
        "minimum_size": size or {"type": "minecraft:two_layers_feature_size", "limit": 1, "upper_size": 1},
        "trunk_placer": trunk, "trunk_provider": _log(log)}}


def straight(base, a=0, b=0): return {"type": "minecraft:straight_trunk_placer", "base_height": base, "height_rand_a": a, "height_rand_b": b}
def forking(base, a=0, b=0): return {"type": "minecraft:forking_trunk_placer", "base_height": base, "height_rand_a": a, "height_rand_b": b}
def fancy(base, a=0, b=0): return {"type": "minecraft:fancy_trunk_placer", "base_height": base, "height_rand_a": a, "height_rand_b": b}
def blob(r, h=3, off=0): return {"type": "minecraft:blob_foliage_placer", "radius": r, "offset": off, "height": h}
def bushf(r, h=2, off=1): return {"type": "minecraft:bush_foliage_placer", "radius": r, "offset": off, "height": h}
def acaciaf(r, off=0): return {"type": "minecraft:acacia_foliage_placer", "radius": r, "offset": off}
def pinef(r, h, off=1): return {"type": "minecraft:pine_foliage_placer", "radius": r, "offset": off, "height": h}
def sprucef(r, off, th): return {"type": "minecraft:spruce_foliage_placer", "radius": r, "offset": off, "trunk_height": th}
def fancyf(r=2, h=4, off=4): return {"type": "minecraft:fancy_foliage_placer", "radius": r, "offset": off, "height": h}
def moss(leaves=0.25, trunk=0.0, ground=0.0):
    return {"type": "minecraft:pale_moss", "leaves_probability": leaves, "trunk_probability": trunk, "ground_probability": ground}
FANCY_SIZE = {"type": "minecraft:two_layers_feature_size", "limit": 0, "upper_size": 0, "min_clipped_height": 4}


def flowers(*blocks, weights=None):
    """Weighted single blocks; a tuple (block, props) for blocks with properties."""
    ws = weights or [1] * len(blocks); entries = []
    for b, w in zip(blocks, ws):
        name, props = (b, None) if isinstance(b, str) else b
        name = _id(name)
        entries.append({"data": {"Name": name, **({"Properties": props} if props else {})}, "weight": w})
    return {"type": "minecraft:simple_block", "config": {"to_place": {"type": "minecraft:weighted_state_provider", "entries": entries}}}


def segmented(block, prop, amounts=(1, 2, 3, 4)):
    entries = [{"data": {"Name": _id(block), "Properties": {"facing": f, prop: str(n)}}, "weight": 1}
               for n in amounts for f in ("north", "east", "south", "west")]
    return {"type": "minecraft:simple_block", "config": {"to_place": {"type": "minecraft:weighted_state_provider", "entries": entries}}}


def column(block, lo, hi, cap=None, cap_chance=0.0):
    layers = [{"height": {"type": "minecraft:biased_to_bottom", "min_inclusive": lo, "max_inclusive": hi}, "provider": _state(_id(block), age="0")}]
    if cap:
        k = max(1, round(cap_chance * 100))
        layers.append({"height": {"type": "minecraft:weighted_list", "distribution": [{"data": 0, "weight": 100 - k}, {"data": 1, "weight": k}]}, "provider": _state(_id(cap))})
    return {"type": "minecraft:block_column", "config": {"allowed_placement": {"type": "minecraft:matching_block_tag", "tag": "minecraft:air"},
            "direction": "up", "layers": layers, "prioritize_tip": False}}



class Ref(str):
    """An existing configured feature, by id."""


def ref(ident): return Ref(_id(ident))


NAMES = {f.__name__: f for f in (tree, straight, forking, fancy, blob, bushf, acaciaf, pinef, sprucef, fancyf, moss, U,
                                 flowers, segmented, column, ref)}
NAMES["FANCY_SIZE"] = FANCY_SIZE
