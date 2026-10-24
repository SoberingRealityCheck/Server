"""Pack plant palette: real plants mapped to Minecraft features, from vanilla blocks or the pack's flora mods
(Biomes O' Plenty, Wilder Wild, Terrestria).

Flora profiles (flora/*.py) name these plants. Each entry is one of
  tree    a configured tree feature (custom JSON, or "ref" to an existing configured feature)
  shrub   the same, placed like trees but counted from shrub cover
  ground  a block or weighted set of blocks scattered in patches (grass, flowers, litter)
  cactus  a block column on sand or dirt (a profile's cactus list may also name ground plants)
Leaves that take the biome foliage colour (oak, acacia, jungle, dark oak, mangrove) pick up the variant's
measured canopy colour; spruce and birch leaves keep their fixed colours.
"""

DIRT = {"type": "minecraft:rule_based_state_provider", "rules": [{"if_true": {"type": "minecraft:not", "predicate": {
    "type": "minecraft:matching_block_tag", "tag": "minecraft:cannot_replace_below_tree_trunk"}},
    "then": {"type": "minecraft:simple_state_provider", "state": {"Name": "minecraft:dirt"}}}]}


def _state(name, **props): return {"type": "minecraft:simple_state_provider", "state": {"Name": name, **({"Properties": props} if props else {})}}
def _log(b): return _state(b, axis="y")
def _leaves(b): return _state(b, distance="7", persistent="false", waterlogged="false")
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
        entries.append({"data": {"Name": name, **({"Properties": props} if props else {})}, "weight": w})
    return {"type": "minecraft:simple_block", "config": {"to_place": {"type": "minecraft:weighted_state_provider", "entries": entries}}}


def segmented(block, prop, amounts=(1, 2, 3, 4)):
    entries = [{"data": {"Name": block, "Properties": {"facing": f, prop: str(n)}}, "weight": 1}
               for n in amounts for f in ("north", "east", "south", "west")]
    return {"type": "minecraft:simple_block", "config": {"to_place": {"type": "minecraft:weighted_state_provider", "entries": entries}}}


def column(block, lo, hi, cap=None, cap_chance=0.0):
    layers = [{"height": {"type": "minecraft:biased_to_bottom", "min_inclusive": lo, "max_inclusive": hi}, "provider": _state(block, age="0")}]
    if cap:
        k = max(1, round(cap_chance * 100))
        layers.append({"height": {"type": "minecraft:weighted_list", "distribution": [{"data": 0, "weight": 100 - k}, {"data": 1, "weight": k}]}, "provider": _state(cap)})
    return {"type": "minecraft:block_column", "config": {"allowed_placement": {"type": "minecraft:matching_block_tag", "tag": "minecraft:air"},
            "direction": "up", "layers": layers, "prioritize_tip": False}}


# kind, feature, sapling used for the survival check, why
PLANTS = {
    # ---- pines and other conifers
    "loblolly_pine":   ("tree", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(11, 4, 2), blob(2, 3, 0)), "minecraft:spruce_sapling",
                        "Tall bare trunk, rounded crown at the top. Piney Woods, Gulf coastal plain."),
    "shortleaf_pine":  ("tree", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(8, 3, 1), pinef(2, U(3, 4))), "minecraft:spruce_sapling",
                        "Smaller pine of the drier uplands: Ozarks, Piney Woods ridges."),
    "longleaf_pine":   ("tree", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(13, 4, 0), blob(2, 2, 0)), "minecraft:spruce_sapling",
                        "Very tall, thin, open crown over grass."),
    "ponderosa_pine":  ("tree", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(10, 4, 2), pinef(2, U(4, 5))), "minecraft:spruce_sapling",
                        "Open park-like pine of the dry western mountains."),
    "pinyon_pine":     ("tree", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(2, 1, 0), blob(2, 3, 0)), "minecraft:spruce_sapling",
                        "Short, round, bushy nut pine of the high desert."),
    "ashe_juniper":    ("ref", "wilderwild:juniper", "minecraft:oak_sapling", "Dense dark 'cedar' brakes of the Hill Country (Wilder Wild juniper)."),
    "one_seed_juniper": ("shrub", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(1, 1, 0), bushf(2, 2, 1)), "minecraft:spruce_sapling",
                        "Low rounded juniper on desert slopes."),
    "eastern_red_cedar": ("tree", tree("minecraft:spruce_log", "minecraft:spruce_leaves", straight(4, 2, 0), sprucef(U(1, 2), U(0, 1), U(1, 2))), "minecraft:spruce_sapling",
                        "Narrow cone; spreads into old prairie and fields."),
    "bald_cypress":    ("ref", "wilderwild:swamp_cypress", "wilderwild:cypress_sapling", "Swamp and river conifer with vines (Wilder Wild swamp cypress)."),
    "douglas_fir":     ("ref", "minecraft:spruce", "minecraft:spruce_sapling", "Mountain fir (vanilla spruce)."),
    "spruce":          ("ref", "minecraft:spruce", "minecraft:spruce_sapling", "Vanilla spruce."),
    "mega_spruce":     ("ref", "minecraft:mega_spruce", "minecraft:spruce_sapling", "Vanilla giant spruce."),
    "subalpine_fir":   ("ref", "minecraft:pine", "minecraft:spruce_sapling", "Narrow spire fir near the treeline (vanilla pine)."),
    # ---- oaks and broadleaves
    "live_oak":        ("tree", tree("minecraft:oak_log", "minecraft:oak_leaves", forking(3, 1, 1), acaciaf(3)), "minecraft:oak_sapling",
                        "Low, very wide evergreen oak with spreading limbs."),
    "live_oak_mossy":  ("tree", tree("minecraft:oak_log", "minecraft:oak_leaves", forking(3, 1, 1), acaciaf(3), decorators=[moss(0.3)]), "minecraft:oak_sapling",
                        "Coastal live oak hung with Spanish moss (pale hanging moss)."),
    "post_oak":        ("tree", tree("minecraft:oak_log", "minecraft:oak_leaves", straight(3, 2, 0), blob(2, 3, 0)), "minecraft:oak_sapling",
                        "Gnarled medium oak of the Cross Timbers and post oak savanna."),
    "blackjack_oak":   ("shrub", tree("minecraft:oak_log", "minecraft:dark_oak_leaves", straight(2, 1, 0), bushf(2, 2, 1)), "minecraft:oak_sapling",
                        "Scrubby dark-leaved oak under the post oaks."),
    "shin_oak":        ("shrub", tree("minecraft:oak_log", "minecraft:oak_leaves", straight(1, 0, 0), bushf(2, 1, 0)), "minecraft:oak_sapling",
                        "Knee-high oak thickets on sand and limestone."),
    "white_oak":       ("ref", "minecraft:fancy_oak", "minecraft:oak_sapling", "Big rounded upland oak (vanilla fancy oak)."),
    "red_oak":         ("ref", "minecraft:oak", "minecraft:oak_sapling", "Vanilla oak."),
    "hickory":         ("tree", tree("minecraft:oak_log", "minecraft:oak_leaves", fancy(6, 4, 0), fancyf(2, 4, 4), size=FANCY_SIZE), "minecraft:oak_sapling",
                        "Tall straight broadleaf of oak-hickory woods."),
    "sweetgum":        ("tree", tree("minecraft:oak_log", "minecraft:oak_leaves", straight(7, 3, 0), blob(2, 4, 0)), "minecraft:oak_sapling",
                        "Tall narrow-crowned hardwood of the southern bottoms."),
    "pecan":           ("tree", tree("minecraft:dark_oak_log", "minecraft:oak_leaves", fancy(7, 5, 0), fancyf(2, 4, 4), size=FANCY_SIZE), "minecraft:oak_sapling",
                        "Large riverbottom hickory with dark bark."),
    "cedar_elm":       ("tree", tree("minecraft:oak_log", "minecraft:oak_leaves", straight(4, 2, 0), blob(2, 3, 0)), "minecraft:oak_sapling",
                        "Small-leaved elm of Texas creek bottoms."),
    "cottonwood":      ("tree", tree("minecraft:birch_log", "minecraft:oak_leaves", fancy(8, 5, 0), fancyf(2, 4, 4), size=FANCY_SIZE), "minecraft:oak_sapling",
                        "Pale-barked giant along prairie and desert rivers."),
    "gambel_oak":      ("shrub", tree("minecraft:oak_log", "minecraft:oak_leaves", straight(2, 1, 0), bushf(2, 2, 1)), "minecraft:oak_sapling",
                        "Thicket-forming oak on Rocky Mountain foothills."),
    "aspen":           ("ref", "minecraft:birch_tall", "minecraft:birch_sapling", "Quaking aspen stands (vanilla tall birch)."),
    "birch":           ("ref", "minecraft:birch", "minecraft:birch_sapling", "Vanilla birch."),
    "maple":           ("ref", "minecraft:fancy_oak", "minecraft:oak_sapling", "Vanilla fancy oak as a stand-in for maples."),
    "fallen_oak":      ("ref", "minecraft:fallen_oak_tree", "minecraft:oak_sapling", "Old fallen trunk."),
    # ---- dryland trees and palms
    "honey_mesquite":  ("tree", tree("minecraft:dark_oak_log", "minecraft:acacia_leaves", forking(2, 1, 1), acaciaf(2)), "minecraft:acacia_sapling",
                        "Small dark-barked, feathery, multi-stemmed tree of brush country and rolling plains."),
    "huisache":        ("ref", "minecraft:acacia", "minecraft:acacia_sapling", "Flat-topped acacia of South Texas (vanilla acacia)."),
    "texas_ebony":     ("shrub", tree("minecraft:dark_oak_log", "minecraft:dark_oak_leaves", straight(2, 0, 0), bushf(2, 2, 1)), "minecraft:acacia_sapling",
                        "Dense dark thorn shrub of the Tamaulipan thornscrub."),
    "sabal_palm":      ("ref", "wilderwild:small_windmill_palm", "minecraft:dead_bush", "Fan palm of the lower Rio Grande and the Gulf coast (Wilder Wild windmill palm)."),
    "yucca":           ("ref", "terrestria:yucca_palm_tree", "minecraft:dead_bush", "Tree yucca of the Trans-Pecos flats (Terrestria yucca palm)."),
    # ---- shrubs and succulents
    "creosote_bush":   ("ground", flowers("minecraft:bush"), None, "Evenly spaced green shrubs on desert flats (grass-tinted bush)."),
    "sagebrush":       ("ground", flowers("minecraft:bush", "minecraft:short_dry_grass", weights=[3, 1]), None, "Grey-green sage on high plains (grass-tinted bush)."),
    "dead_shrub":      ("ground", flowers("minecraft:dead_bush"), None, "Dry, leafless shrubs."),
    "tumbleweed":      ("ground", flowers(("wilderwild:tumbleweed_plant", {"age": "2"}), ("wilderwild:tumbleweed_plant", {"age": "3"})), None, "Russian thistle that breaks off and rolls (Wilder Wild)."),
    "agave":           ("ground", flowers("terrestria:agave"), None, "Lechuguilla and century plant on desert limestone (Terrestria agave)."),
    "yaupon":          ("ground", flowers("minecraft:bush", "minecraft:firefly_bush", weights=[4, 1]), None, "Evergreen holly understory of the Piney Woods."),
    "prickly_pear":    ("ground", flowers(("wilderwild:prickly_pear", {"age": "0"}), ("wilderwild:prickly_pear", {"age": "1"}), ("wilderwild:prickly_pear", {"age": "2"}), weights=[5, 3, 2]), None,
                        "Low pad cactus with fruit (Wilder Wild prickly pear)."),
    "cholla":          ("cactus", column("minecraft:cactus", 2, 3, "minecraft:cactus_flower", 0.1), None, "Taller column cactus of the Chihuahuan desert."),
    "sugar_cane_reeds": ("ground", flowers(("minecraft:tall_grass", {"half": "lower"}), "minecraft:short_grass", weights=[2, 1]), None, "Marsh grasses."),
    # ---- grasses
    "short_grass":     ("ground", flowers("minecraft:short_grass"), None, "Short grass sward."),
    "tallgrass":       ("ground", flowers(("minecraft:tall_grass", {"half": "lower"}), "minecraft:short_grass", weights=[3, 1]), None, "Big bluestem and switchgrass prairie."),
    "mixed_grass":     ("ground", flowers("minecraft:short_grass", ("minecraft:tall_grass", {"half": "lower"}), "minecraft:short_dry_grass", weights=[4, 2, 1]), None, "Little bluestem mixed-grass prairie."),
    "shortgrass":      ("ground", flowers("minecraft:short_grass", "minecraft:short_dry_grass", weights=[2, 3]), None, "Buffalograss and blue grama: short, curly, dry."),
    "dry_bunchgrass":  ("ground", flowers("minecraft:short_dry_grass", "minecraft:tall_dry_grass", weights=[2, 1]), None, "Sparse desert bunchgrass."),
    "ferns":           ("ground", flowers("minecraft:fern", "minecraft:short_grass", weights=[3, 1]), None, "Fern understory."),
    "leaf_litter":     ("ground", segmented("minecraft:leaf_litter", "segment_amount", (1, 2, 3)), None, "Oak leaf litter."),
    # ---- flowers
    "bluebonnet":      ("ground", flowers("minecraft:cornflower"), None, "Texas bluebonnet: blue spring fields (cornflower)."),
    "indian_paintbrush": ("ground", flowers("terrestria:indian_paintbrush"), None, "Red paintbrush among the bluebonnets (Terrestria)."),
    "indian_blanket":  ("ground", flowers("minecraft:orange_tulip", "minecraft:red_tulip", weights=[3, 1]), None, "Firewheel: red-orange roadside daisies."),
    "coreopsis":       ("ground", segmented("minecraft:wildflowers", "flower_amount"), None, "Yellow coreopsis and black-eyed Susan (wildflowers)."),
    "winecup":         ("ground", flowers("minecraft:allium", "minecraft:pink_tulip", weights=[2, 1]), None, "Magenta winecup and pink evening primrose."),
    "prairie_mix":     ("ground", flowers("minecraft:dandelion", "minecraft:oxeye_daisy", "minecraft:cornflower", "minecraft:azure_bluet", "minecraft:allium"), None, "Mixed prairie forbs."),
    "blue_flag":       ("ground", flowers("minecraft:blue_orchid"), None, "Iris and pickerelweed in marshes (blue orchid)."),
    "desert_marigold": ("ground", flowers("wilderwild:marigold", "minecraft:short_dry_grass", weights=[1, 2]), None, "Sparse yellow desert daisies (Wilder Wild marigold)."),
    "phlox":           ("ground", segmented("wilderwild:phlox", "flower_amount"), None, "Drummond phlox: pink-red carpets on sandy East Texas ground (Wilder Wild)."),
    "lantana":         ("ground", segmented("wilderwild:lantanas", "flower_amount"), None, "Texas lantana, orange and yellow, in brush and Hill Country (Wilder Wild)."),
    "milkweed":        ("ground", flowers(("wilderwild:milkweed", {"age": "0", "half": "lower"})), None, "Antelope-horn milkweed of the prairies (Wilder Wild)."),
    "goldenrod":       ("ground", flowers(("biomesoplenty:goldenrod", {"half": "lower"})), None, "Tall yellow autumn goldenrod (Biomes O' Plenty)."),
    "sea_oats":        ("ground", flowers(("biomesoplenty:sea_oats", {"half": "lower"})), None, "Dune grass of the barrier islands (Biomes O' Plenty)."),
    "datura":          ("ground", flowers(("wilderwild:datura", {"half": "lower"})), None, "Sacred datura, white trumpets on desert washes (Wilder Wild)."),
    "dogwood_bloom":   ("ground", flowers("minecraft:white_tulip", "minecraft:lily_of_the_valley"), None, "White spring blooms under the pines."),
}
