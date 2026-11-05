# Elysium Flora

Thin logs and thin-trunk trees. Fabric, MC 26.2. Needed on server and client (it adds blocks).

Status (2026-11-05): leaf tones added, not yet compiled. Before that (2026-10-28): compiles against 26.2 + Fabric API 0.161.0 and runs on a headless 26.2 server. All four test trees place; leaves next to thin logs did not decay over 150 s of ticking. Not yet looked at in a client (models, textures) or with Distant Horizons.

## Blocks

`elysium_flora:thin_<log>` for oak, spruce, birch, jungle, acacia, dark oak, mangrove, cherry and their stripped logs (16 blocks). No pale oak.

- 6 px core with arms to any of the six faces. A face joins another thin log or any `#minecraft:logs` block. On placement it also joins the clicked face if that is sturdy, and the bottom joins sturdy ground.
- 128 states per block (6 faces x waterlogged), about 2k in total. No block entity, no ticking.
- Textures are the vanilla log's own side and top, cropped by UV. A free face shows end grain where the log runs through it (pole tips), bark otherwise.
- Axe strips it. Burns like a log. In `#minecraft:logs` (leaves next to it do not decay; fuel; charcoal), not in `#oak_logs` etc.

Recipes, 1:1 both ways:

| In | Out |
|---|---|
| 2 logs stacked | 2 thin logs |
| 2 thin logs stacked | 2 logs |
| 1 thin log | 4 planks |

Thin logs are not in `#oak_logs` etc., so those recipes don't double up. A lone log already makes planks, so the swap takes two stacked. Fits the 2x2 grid.

## Tree pieces

| Id | Kind | What it does |
|---|---|---|
| `elysium_flora:multi_stem` | trunk placer | 1-8 stems from one root or a small stool (`spread`), each leaning (`lean`), optional one-off side fork (`fork_chance`). Every stem ends in a crown. Sets the thin logs' faces along the path each stem grew, so stems side by side stay separate. |
| `elysium_flora:connect_thin_logs` | tree decorator | For thin logs placed by other trunk placers (vanilla ones): joins each to every log neighbour. Side-by-side stems fuse into a ladder, so multi_stem trees do not use it. List it last. |
| `elysium_flora:branch_stubs` | tree decorator | Thin side branches on any trunk (thin or full) into air, upper part only. |

Test trees in `data/elysium_flora/worldgen/configured_feature/`: `honey_mesquite`, `quaking_aspen`, `alder_clump`, `oak_with_branches`. In game: `/place feature elysium_flora:honey_mesquite`.

Worldgen use: atlas profiles reference these configured features by id like any other tree. Placed features and per-region species come later, through the atlas profile yaml.

## Leaf tones

Every leaf block, vanilla and modded, gets a `tone` property: `0` none, `1` sun, `2` shade, `3` pale (mixin on `LeavesBlock`; 28 -> 112 states per leaf block, default 0, so existing worlds and blockstate files are unchanged). The client shifts the leaf's tint, whatever set it (vanilla, the atlas's region palettes, Serene Seasons), so toned leaves follow seasons and regions. One leaf block with tones counts as one leaf type.

| Tone | Shift (CIE Lab) | Use |
|---|---|---|
| sun | L +14, b +22 (warmer) | sun-facing tops, outer tips, early-turning clumps |
| shade | L -22 | crown interior, north side |
| pale | L +26, chroma x0.3 | undersides (white poplar, whitebeam), frost, snow load |

Contrast floor: each tone is at least dE76 24 from the base on a leaf face (tint x 0.62, the leaf textures' mean grey); where the sRGB gamut clips, the shift grows in steps until it is. Worst case over vanilla, autumn and winter bases is about 20; a base near black can't get a darker shade. Tuning script: `tree-studies/tone.py` in the project files (same numbers as `client/ToneColors`).

Untinted leaves (cherry, azalea, fixed-colour mod leaves such as BOP maples) carry the property but show no change. For those use the decorator's `block` swap.

`elysium_flora:leaf_tones` (tree decorator) picks leaves by rule in one pass over the tree's leaves and sets a tone, swaps the block (a second leaf block for blossom, berries, snow or bare twigs; distance, persistent and waterlogged are kept), or both. Layers apply in order; a later one wins.

```json
{"type": "elysium_flora:leaf_tones", "layers": [
  {"rule": "sun_cap", "tone": "sun", "chance": 0.9},
  {"rule": "shade", "tone": "shade"},
  {"rule": "tips", "chance": 0.6, "block": {"type": "minecraft:simple_state_provider", "state": {"Name": "minecraft:flowering_azalea_leaves"}}}]}
```

| Rule | Picks | `param` |
|---|---|---|
| `sun_cap` | top of each leaf column | layers down from the top (1) |
| `underside` | bottom of each leaf column | layers up from the bottom (1) |
| `shade` | interior: all six neighbours leaves or wood | |
| `rim` | silhouette: a horizontal neighbour open | |
| `tips` | farthest from wood, in steps through leaves | outer layers (1) |
| `gradient` | dithered (4x4 Bayer) by height, top heavy | 1 = bottom heavy |
| `sunny_side` | half of the crown facing `direction` (south) | |
| `patches` | whole cells, so tones come in clumps; `chance` is per cell | cell size (3) |
| `random` | any leaf | |

`chance` (default 1) is per leaf except for `patches`. At most two leaf blocks per tree (pack rule).

Demo trees: `toned_oak` (sun cap + shade interior), `toned_aspen` (sun patches), `pale_underside_birch`, `snow_load_spruce` (pale cap), `blossom_tips_oak` (dithered sun + flowering azalea tips).

## Files

- `src/main/java/dev/elysium/flora/`: `ElysiumFlora` (registration), `ThinLogBlock`, `LeafTone`, `worldgen/`, `client/` (tone colours), `mixin/` (`LeavesBlockMixin`; `client/BlockColorsMixin`, a `@WrapMethod` on `getTintSources` so the tone lands on top of the atlas's leaf tints).
- `tools/gen_assets.py`: writes every JSON under `src/main/resources/assets` and `data` (blockstates, models, items, lang, loot, recipes, tags, test trees). Edit it, not the JSON.
- `build.sh`: plain javac like `elysium-atlas/build.sh`; writes `../overrides/mods/elysium_flora.jar`.

## To check in game

- Models and textures in a client (bark grain on horizontal arms, end grain on tips).

- Leaf tones: demo trees in a client, with the atlas tints and Serene Seasons on, with Sodium, and in Distant Horizons LODs.
- Distant Horizons SeedGen draws the test trees (it runs the same feature code).
- F3 frame time in a dense stand of `alder_clump` versus vanilla oak.
