# Plant and ecoregion database

The regional flora of the pack. Plain YAML, read by `variants/db.py`; `variants/biome_variants.py` turns it into
the biome variants, plant features and colour tables in `src/main/resources`. Edit here, then regenerate.

```
db/
  colours.yaml          named summer leaf colours (fresh_green, dark_blue_green, ...)
  plants/*.yaml         one entry per species, grouped by continent; common.yaml for cosmopolitan plants and cover
  ecoregions/*.yaml     one entry per RESOLVE ecoregion: which species grow there, and how much
```

Rule: every plant is a real species with a Latin name, and every colour comes from a species. Ecoregions do not
set colours. The only non-species entries are `form: cover` (leaf litter, mosses, fallen logs, dead brush); they
never count in colours.

## Plant entry

```yaml
loblolly_pine:                       # id, used in ecoregion lists
  name: Loblolly pine
  latin: Pinus taeda
  form: tree                         # tree | shrub | shrub_ground | grass | fern | herb | flower | succulent | cactus | cover
  leaf: yellow_green_pine            # trees and shrubs: summer leaf colour, a colours.yaml name or "#rrggbb"
  leaf_note: Yellow-green needles in threes, 15-23 cm.   # what the colour is based on
  autumn: "#a8662a"                  # optional, not used yet
  range: Piney Woods, Gulf coastal plain.
  look: Tall bare trunk, rounded crown at the top.
  render: 'tree("spruce_log", "spruce_leaves", straight(11, 4, 2), blob(2, 3, 0))'
  sapling: spruce_sapling            # trees: the sapling whose survival rule decides where it may grow
  stand_in: Vanilla spruce.          # when the blocks stand for something they are not
  niche: {water: dry}                # optional, see Niches
  clump: {size: 40, share: 0.5}      # optional, see Clumping
```

Grasses use `colour` / `colour_note` instead of `leaf`: the colour of the turf, which becomes the grass tint.

`render` is one call of a builder from `variants/render.py` (tree, ref, flowers, segmented, column and the
trunk and crown shapes listed there). Ids without a namespace are `minecraft:`. `ref("biomesoplenty:fir_tree")`
uses an existing vanilla or flora-mod feature.

## Ecoregion entry

```yaml
689:                                 # RESOLVE Ecoregions 2017 ECO_ID
  name: Alpine Forest                # in-game biome name
  resolve: "Alps conifer and mixed forests"
  tree_cover: 0.5                    # share of land under trees (default from the WWF habitat type)
  trees: {norway_spruce: 4, silver_fir: 2, european_larch: 2, arolla_pine: 1, european_beech: 1}
  shrubs: {mountain_pine: 2, green_alder: 1}
  ground: {bilberry: 1, blue_moor_grass: 1.5, mat_grass: 1.5}   # must name at least one grass
  flowers: {spring_gentian: 3, alpine_pasqueflower: 2}
  flower_density: 1.2                # patches per chunk; also tree_density, shrub_density, cactus, cactus_density
  rebase: {minecraft:swamp: minecraft:forest}   # atlas biome -> parent the variant inherits from instead
  niches:                            # optional: where in this region each species grows, see Niches
    norway_spruce: {elevation: [800, 2050]}
    european_larch: {elevation: [1300, 2400]}
  clumps: {live_oak: {size: 20, share: 0.4}, heather: none}    # optional: override plant clumps here
  patches:                           # optional: whole layers in patches with open ground between
    trees: {size: 48, share: 0.65}
  ground_surface:                    # optional: rock and soil, see Ground surface
    geology: "Crystalline core and limestone ranges; scree below cliffs."
    rock: [stone, calcite]           # one or two blocks; steep ground and outcrops
    outcrops: some                   # none | few | some | many
    soil: {gravel: few}              # up to three patch blocks, each none | few | some | many
    top: coarse_dirt                 # optional: the top block everywhere else (deserts: bare soil, no grass)
    subsoil: calcite                 # optional: replaces the dirt under the top block
  why: "One line on what the region is."
```

Numbers in a layer are relative weights. How many trees a chunk gets comes from `tree_cover`, the atlas biome's
own tree count and `tree_density`.

## Niches

A niche says where a species grows within its ecoregion. Keys:

| key | values | effect |
|---|---|---|
| `elevation` | `[low, high]` metres | full weight inside the band, fading to zero over 150 m past each edge |
| `water` | `riparian`, `wet`, `dry`, `any` | riparian: river and lake banks (about 25 blocks); wet: banks or waterlogged ground; dry: avoids banks |
| `slope` | `flat`, `steep`, `any` | steep: cliffs and scarps; flat: level ground |

A plant's own `niche` holds what is true everywhere (bald cypress is wet). Elevation belts differ by latitude and
range, so they go in the ecoregion's `niches`, which override the plant's per key; `any` lifts a key in one region
(pecan grows across the whole Mississippi floodplain, not only on banks).

At each spot every species' weight is multiplied by how well the spot suits it. The plant count thins with the
best suitability of any listed species: where one fits fully the density is full, and ground that suits
none (above the treeline) gets nothing.
Elevation is read from the ground height through the atlas vertical scale (`Atlas.elevationMetres`, 18.75 m per
block above sea level). Placement: `elysium_atlas:niche_selector` (`NicheSelectorFeature.java`).

## Clumping

Plants grow in patches. A clump is `{size, share, outside}`: patches about `size` blocks across cover `share` of
the ground, and `outside` (default 0.1) is how much of the plant grows between them.

- `clump` on a plant (or `clumps` in an ecoregion) moves that species' weight into its own patches without changing
  its total: aspen groves, cedar brakes, bluebonnet fields, bluebell carpets. Flowers default to
  `{size: 12, share: 0.35}`, so each drift is mostly one species; `none` turns a clump off.
- `patches` in an ecoregion gathers a whole layer (trees, shrubs, ground or flowers) into patches with open ground
  between: oak mottes in the Hill Country, forest and meadow in the Alps, groves in the forest steppe. The
  placement count rises by 1 / (outside + (1 - outside) x share) so the mean density stays the same.

Each species and layer has its own noise pattern (`Clump.java`, two octaves of value noise; `share` is exact for any
size).

## Ground surface

`ground_surface` sets the top block on dry, non-snow, non-beach ground of the region's variants:
steep ground and `outcrops` become `rock`, then `soil` patches, then `top` (if given) everywhere else; `subsoil`
replaces the dirt below the top.
Bedded rock (all optional; conditions in `ElysiumSurfaceConditions.java`):
- `ledges: {every, keep}`: on ground with exactly a 1-block rise to a neighbour, rock on one Y row in `every`,
  `keep` of it (noise-broken). Reads as ledge lines along the contours.
- `strata: [blocks]`: on 2+ block steps, the top and the exposed face below take the block of their Y row (Y mod length).
- `banks: {blocks, distance}`: within `distance` blocks of an atlas river or stream channel (the bed included),
  the first block, mixed half and half with the second if given.
- `outcrop_size: small`: outcrops as 2-5 block fragments instead of 15-30 block patches.

Shares: few 5 %, some 12 %, many 25 % of eligible ground, from normal noises with measured sd 0.31
(`biome_variants.SURFACE_NOISES`). Outcrops are about 15-30 blocks across and soil patches 8-16, so a small area can sit
above or below its share. Written as a Lithostitched surface rule,
`data/elysium_atlas/lithostitched/worldgen_modifier/regional_surface.json`.

## Derived colours

For each ecoregion (`db.colours`):

| colour | from |
|---|---|
| grass tint | weighted mean of the `colour` of the grasses in `ground` |
| foliage tint | weighted mean of the `leaf` colour of all trees and shrubs (the grass tint where there are none) |
| each leaf block (spruce, oak, birch, BOP fir ...) | weighted mean of the `leaf` colour of the species that grow that block |

The leaf colours are stored per variant biome as offsets from its foliage (`leaf_palettes.json`), so seasons still
shift them. Species that share a leaf block in game share its colour in a region.

Colours are taken from each species' usual description (`leaf_note`, `colour_note`), not measured from photographs.

Season colours come from `seasons/` (see `variants/seasons.py`): `species_phenology.yaml` (leaf tracks of deciduous
species; evergreens keep `leaf` all year), `grass_phenology.yaml`, `region_climate.yaml` (phase and winter class per
region; add `grass: summer_dry` where perennial grass cures in summer under a snowy winter) and the hand-authored
`season_palettes.yaml`. These are copies of the art direction files in the project folder; edit them here.

## Checks

`db.py` stops the build on: an unknown plant id, a species without `latin`, a tree or shrub without a leaf colour,
a grass without a colour, an ecoregion without a grass, a render that calls anything outside `render.py`,
a niche with an unknown key or value, a `niches` entry for a species the ecoregion does not list, a `ground_surface`
with an unknown key or amount.

In game, `/atlas here` prints the ecoregion, its colours and its species (from `elysium_atlas/ecoregions.json`).
