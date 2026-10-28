# Elysium Flora

Thin logs and thin-trunk trees. Fabric, MC 26.2. Needed on server and client (it adds blocks).

Status: written, **not yet compiled or run**. The container that wrote it cannot reach Mojang or the Fabric maven, so the first build needs `build.sh` run where those are reachable (Clay's Mac).

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

A lone log already makes planks, so the swap takes two stacked. Fits the 2x2 grid.

## Tree pieces

| Id | Kind | What it does |
|---|---|---|
| `elysium_flora:multi_stem` | trunk placer | 1-8 stems from one root or a small stool (`spread`), each leaning (`lean`), optional one-off side fork (`fork_chance`). Every stem ends in a crown. No AXIS: works with thin logs. |
| `elysium_flora:connect_thin_logs` | tree decorator | Joins the faces of every thin log the trunk placer put down. List it last. |
| `elysium_flora:branch_stubs` | tree decorator | Thin side branches on any trunk (thin or full) into air, upper part only. |

Test trees in `data/elysium_flora/worldgen/configured_feature/`: `honey_mesquite`, `quaking_aspen`, `alder_clump`, `oak_with_branches`. In game: `/place feature elysium_flora:honey_mesquite`.

Worldgen use: atlas profiles reference these configured features by id like any other tree. Placed features and per-region species come later, through the atlas profile yaml.

## Files

- `src/main/java/dev/elysium/flora/`: `ElysiumFlora` (registration), `ThinLogBlock`, `worldgen/`.
- `tools/gen_assets.py`: writes every JSON under `src/main/resources/assets` and `data` (blockstates, models, items, lang, loot, recipes, tags, test trees). Edit it, not the JSON.
- `build.sh`: plain javac like `elysium-atlas/build.sh`; writes `../overrides/mods/elysium_flora.jar`.

## To check in game

- Leaves next to thin logs do not decay (tag name for 26.2 leaf decay to confirm).
- Distant Horizons SeedGen draws the test trees (it runs the same feature code).
- F3 frame time in a dense stand of `alder_clump` versus vanilla oak.
