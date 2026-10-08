# Minecraft

## Current server

| | |
|---|---|
| Version | 26.2 |
| Loader | Fabric |
| Port | 25565/TCP |
| Profile | Elysium |

Terralith/Tectonic worldgen, Distant Horizons LOD rendering, performance
and QOL mods, layered under the Matcha Flavoured and Path Generator
datapacks. Full contents: `MODLIST.md` (generated -- see below).

## How the pack works

`pack.yaml` is the source of truth. `build.py` compiles it into
`dist/pack.mrpack`, a [Modrinth
modpack](https://support.modrinth.com/en/articles/8802351-modrinth-modpack-format-mrpack):
a zip containing `modrinth.index.json` plus anything in `overrides/`.

That one artifact serves both sides. Each entry in `pack.yaml` declares
where it belongs:

| `env` | Server installs it | Client installs it |
|---|---|---|
| `both` | yes | yes |
| `server` | yes | no |
| `client` | no | yes |

The server reads the pack via `MODRINTH_MODPACK` and installs only what
is marked server-side. Players import the same file into a launcher and
get only the client-side set. This replaces the old
`mods/server` + `mods/client` split, where shared mods were listed twice
and client mods were documented-but-manual.

### Building

```bash
./build.py               # writes dist/pack.mrpack and MODLIST.md
./build.py --check       # verify hashes, write nothing
./build.py --check-deps  # verify mod dependencies per side
./build.py --check-env   # verify each mod is on the sides upstream requires
./build.py --offline     # build from cache, no network
./build.py --clean       # drop the download cache
./build.py --resolve SLUG  # print an updated block for a Modrinth project
```

### Datapacks and sides

Datapacks default to server-only, and for a pure datapack that is
correct: recipes, loot tables, worldgen and advancements are
server-authoritative and reach clients as ordinary game state over the
network. Players need no file.

The exception is a pack that ships **data and assets in one zip**. The
server reads `data/`, the client reads `assets/` -- and textures and
lang strings are not networked. Without the client half the player sees
missing textures and raw translation keys. Mark those with:

```yaml
    resourcepack: true
```

Matcha Flavoured is one of these; Path Generator is not.

Some authors ship the resource pack as a separate download instead of
one combined zip (Matcha did from 1.12). For those, make `resourcepack`
a block with its own `file`, `url` and `sha512` rather than `true`. The
server pushes that file and installs the datapack zip as usual.

The client half is **not** shipped inside the `.mrpack`. A `.mrpack` can
place a file in `resourcepacks/` but cannot enable it, which would leave
every player a manual toggle to discover. Instead the server pushes it:
`build.py` writes `dist/resourcepack.env` with the pack's URL and SHA1,
`docker-compose.yml` loads that as an `env_file`, and Minecraft prompts
each client on join.

Both values are derived from the same pinned entry the server installs,
so the pushed pack cannot drift from the installed data. The file is
regenerated on every build and cleared when no datapack is flagged, so a
removed pack stops being pushed.

Only one datapack may set the flag -- `server.properties` holds a single
resource-pack URL, and `build.py` rejects a second rather than silently
choosing.

Declining the download leaves a player with untextured items rather than
kicking them. Set `MC_RESOURCE_PACK_ENFORCE=true` in `.env` to require
it instead; that guarantees everyone sees the same game at the cost of
locking out anyone whose download fails.

### HUD and map settings

All client side. The pack sets none of these, so each player tunes their own.

- **Hotbar / health / hunger:** AutoHUD. Options -> Mod Menu -> AutoHUD
  (it uses YACL). Each HUD part has its own hide delay and fade.
- **Crosshair:** Dynamic Crosshair. Same place.
- **Minimap:** Xaero's Minimap. Press `Y` in game for its settings (size,
  zoom, opacity, position). If it's too big, shrink the size and lower
  opacity first. Xaero's default keys can differ, so check Options ->
  Controls.
- **World map:** `M`. Its gear icon has its own settings.

### Known issue: shaders + Distant Horizons

**Symptom.** With shaders enabled, distant terrain renders as vertical
smears, the world looks inside-out, and geometry that should be hidden
draws over everything. The minimap looks normal, which is the tell that
the world data is fine and only rendering is broken.

**Fix, in the moment.** Force Iris to rebuild its render targets:

- Drag the window edge a few pixels and drag it back, **or**
- Toggle shaders off and on again from Video Settings

Either works immediately. It comes back on relaunch or sometimes after
alt-tabbing, and the same fix applies again.

**Why.** At pipeline init, DH's LOD pass ends up bound to framebuffer
dimensions that do not match the real drawing surface, so LOD geometry
rasterises at the wrong scale. Both workarounds force a rebuild at the
correct size. It is an upstream Iris/DH bug, not a pack
misconfiguration -- do not go changing DH settings to chase it.

macOS is especially prone: on a Retina display the window size and
backing pixel size differ by 2x, and Iris additionally force-disables
instanced rendering on macOS when Sodium is present.

Trying fullscreen at launch is worth a shot -- if the surface never
resizes after init, the bad path may not trigger.

**Also expected, and not a bug:** under Iris, distant LODs render
untextured. DH 3.2.0's LOD textures apply only to base DH rendering.
Shaders and maximum distant-terrain fidelity are partly at odds; pick
whichever you want more.

### Dependency checking

`--check-deps` opens every jar, reads its real `fabric.mod.json`, and
resolves the same constraints Fabric evaluates at launch -- including
the modules nested inside Fabric API, which mods commonly depend on
directly.

It checks the client and server sets **separately**, because they get
different subsets. A mod marked `server` that should be `both` leaves
its dependents unsatisfied on the client, and that only surfaces when a
player launches the game. This catches it at build time.

Output is one of `CONFLICT` (present but wrong version), `MISSING` (not
in that side's set), `BREAKS` (a mod declares hard incompatibility with
something present), or `unchecked` (a version range in a syntax the
checker does not parse -- reported rather than silently passed).

Two things this got wrong early on, both worth remembering:

- **Version components.** Minecraft mods routinely use four
  (`26.2.0.9`). Truncating to three made every `26.2.0.x` compare equal,
  so `>=26.2.0.6` silently passed against `26.2.0.2`.
- **`breaks` is a separate field from `depends`.** Reading only the
  latter missed "World Map is incompatible with Minimap `<26.4.0`"
  entirely -- a constraint that stops the game from starting.

CI runs this on every push and PR.

### Side checking

`--check-deps` has a blind spot it cannot close: it verifies that every
mod *present* has its dependencies satisfied. A mod wrongly marked
`server` is simply absent from the client set, so it declares nothing
and violates nothing. Fabric starts happily. Players just find that a
feature does nothing, with no error anywhere to explain why.

`--check-env` closes it from the other direction. Modrinth publishes
each project's `client_side` and `server_side` requirement, and this
compares that against the `env` in `pack.yaml`:

- **MISSING** -- upstream marks a side `required`, our `env` excludes it.
  Players silently lose the feature. This is the case that bit us with
  Easy Shulker Boxes and Bundle Upgrade.
- **EXTRA** -- upstream marks a side `unsupported`, our `env` ships it
  there anyway. Usually harmless, occasionally a crash.

`optional` never forces anything, so a mod that works on both sides is
free to be `client`, `server`, or `both`.

Upstream metadata is author-maintained and occasionally wrong. To
deviate deliberately, record why:

```yaml
    env_override: "ships client-side too, upstream metadata is stale"
```

That silences the check for that entry and leaves the reasoning in the
manifest rather than in someone's memory.

CI runs this on every push and PR. It calls the Modrinth API, so an
upstream outage will fail the run -- an accepted trade, since a
client-less mod is far more expensive to discover than a re-run.

Requires [uv](https://docs.astral.sh/uv/). `build.py` is a uv script (PEP
723 inline metadata) -- uv installs PyYAML into an isolated env on first
run, no venv or pip install needed. If `./build.py` isn't executable,
run `uv run build.py` instead.

`build.py` downloads each artifact once (cached in `.cache/`, keyed by
hash) to verify its pinned sha512 and derive the sha1 and byte size the
format requires. A hash mismatch fails the build -- so an upstream file
that changed under a pinned URL gets caught here rather than on the
server.

`MODLIST.md` is regenerated on every build. Do not edit it by hand;
edit `pack.yaml`.

### Pinning the loader version

`loader_version: "latest"` makes `build.py` resolve the newest stable
Fabric Loader at build time and print what it picked. Copy that value
into `pack.yaml` for reproducible builds -- otherwise two builds a month
apart can produce different packs from identical source.

### overrides/

Files here are copied verbatim into the instance, at the same relative
path, on both sides. Use it for mod configs you want consistent across
players. Currently empty.

`client-overrides/` works the same way but only players get it. Currently
empty on purpose. A launcher can re-apply override files on a pack
update and wipe a player's own tweaks. So the shader settings below live
in this README and are not shipped.

### local-mods/

Each folder here is the source of a small mod that `build.py` zips into a
jar and puts in the pack. Which side gets it comes from `environment` in
its `fabric.mod.json`. Use it for data that a mod reads, so players get it
with no setting to turn on. A resource pack would be a toggle to find.

`elysium-ambience` is data for AmbientSounds. It has two rules:

- `leaf-wind`: wind in leaves near trees on the surface. Quiet in clear
  weather (0.2), louder in rain and storms (0.45).
- `river`: a stream sound in river biomes when water is nearby (0.35).
  The two audio files are copied from the Dynamic Surroundings Sounds
  Pack (GPL-3.0). That pack only plays its own river sound when a
  salmon makes noise, so this rule fills the gap. Hack: it keys on the
  river biome tags, not on flowing water, because AmbientSounds can't
  tell flowing water from still. Streams Reflowing streams outside river
  biomes stay silent.

Untested in game. The river volume and region are guesses.

### Resource packs

Resource packs declared in `pack.yaml` are installed for clients under
`resourcepacks/`, but launchers cannot enable them automatically. Turn
Dynamic Surroundings Sounds Pack on under Options -> Resource Packs. It
runs alongside AmbientSounds and Presence Footsteps, not instead of them.
Expect overlap. Footsteps may double up, and the pack's own ambient
events can stack on AmbientSounds loops. If it sounds muddy, turn the
resource pack off first. Also listen for conflicts with Cool Rain and
Hear the Wind.

The pack is GPL-3.0. Its project page credits Dynamic Surroundings,
Presence Footsteps and AmbientSounds 6 and describes asset licensing;
see the [project page](https://modrinth.com/resourcepack/dynamic-surroundings-sounds-pack)
for those credits and asset notes.

`server-overrides/` works the same way but only the server gets it.
`server-overrides/world/datapacks/z-footpath-terralith/` extends Path
Generator to Terralith's ground blocks (gravel, clay, mud, granite,
calcite and so on). It replaces the base pack's `footpath:convert`
function whole, so if Path Generator updates, re-copy its
`convert.mcfunction` into ours first. The `z-` prefix makes it load
after Path Generator, which is what lets it win.

Server-side settings that the container can set as environment variables
(difficulty, MOTD, view distance, whitelist) belong in `.env` instead --
see the root README.

## For players

Download the `.mrpack` from the repo's
[Releases](../../../releases) page and import it:

- **Modrinth App**: Add Instance → From File
- **Prism Launcher**: Add Instance → Import → select the file

The launcher installs Fabric and the client-side mods automatically.
Nothing needs to be matched by hand against a server list.

Each release also carries a generated `MODLIST.md` describing exactly
what that version contains.

### Settings that worked well for me

Complementary Reimagined is the one shader in the pack. It is installed
but not turned on. Turn it on under Video Settings, Shaders. These are
the settings I use, under Shader Pack Settings. They are a starting
point. Change whatever you like.

| Setting | Value |
|---|---|
| Water Reflection Quality | Sky only |
| Block Reflection Quality | Low |
| Real-Time Shadows | Low |
| Light Shaft Quality | Low |
| Cloud Quality | Low |
| Entity Shadows | OFF |
| Anti-Aliasing (FXAA) | OFF |

Why sky-only water reflections? The default (Medium) reflects only what
is on screen. Under a tree canopy the reflection has nothing to show for
the hidden parts, so it smears the nearest pixel into streaks. Sky only
has no streaks, but the water no longer mirrors trees.

Clouds. Distant Horizons turns off vanilla clouds when it loads, and
Better Clouds only draws when vanilla clouds are on. If you see no
clouds, open the Distant Horizons settings, go to Advanced Options,
Graphics, and turn off Override Vanilla Settings. Then turn Clouds back
on in Video Settings. With it off, the seam between normal terrain and
distant terrain may flicker a little.

The pack is not published on modrinth.com. The tradeoff is that
launchers cannot auto-detect updates, so a new release means downloading
and re-importing. In exchange, deploys never wait on Modrinth's modpack
review queue, and the server installs from a local file rather than
depending on an external service at boot.

Distant Horizons, JEI, and Jade are marked `both` because they genuinely
need a copy on each side -- the server generates LOD data, stores
recipes, and supplies block metadata; the client renders it.

## Changing the pack

1. Edit `pack.yaml` -- add, remove, or bump an entry. Get the URL and
   sha512 from the file's Modrinth version page, or have `build.py`
   fetch them:

   ```bash
   ./build.py --resolve fabric-api
   ```

   That prints a paste-ready block for the newest build matching the
   pack's Minecraft version and loader, and lists the project's required
   dependencies on stderr so you can check the pack still satisfies
   them. It prints rather than editing `pack.yaml` in place -- PyYAML
   cannot round-trip a file without discarding comments, and the
   reasoning in those comments is worth more than the typing saved.
2. Bump `version` in `pack.yaml`.
3. `./build.py` to check it locally, then commit and push `pack.yaml`.
   You do not need to commit `MODLIST.md` -- CI regenerates and commits
   it for you.
4. Deploy: `docker compose up -d --force-recreate minecraft` from the
   repo root.

Pushing the version bump is what publishes the release. There is no
separate tagging step.

## Releases

`.github/workflows/pack.yml` is driven entirely by `version` in
`pack.yaml`:

| You push | CI does |
|---|---|
| Mod changes, same version | Builds, verifies hashes and dependencies, updates `MODLIST.md` |
| Mod changes, bumped version | All of the above, then tags `v<version>` and publishes a release |
| A pull request | Builds and verifies only; nothing is written or published |

The tag is derived from the manifest rather than typed by hand, so the
two cannot disagree. Re-running on an already-released version is a
no-op, not an error, which keeps re-runs safe.

`MODLIST.md` is generated from `pack.yaml`, so CI regenerates and
commits it rather than failing and asking you to. That commit carries
`[skip ci]` so it does not trigger another run, and the release tag
points at it, meaning the tagged tree matches the published assets.

Downloaded jars are cached between runs, keyed by `pack.yaml`'s contents
-- change a pinned hash and the cache key changes with it, so a stale jar
can never be reused for a new pin.

### Building without a release

To build on demand -- to sanity-check a `pack.yaml` edit, or just to get
a `.mrpack` -- use **Actions → pack → Run workflow**. The built pack is
attached to the run as an artifact named `pack.mrpack`, downloadable
from the run summary for 14 days. Manual runs and PR builds never
publish a release.

Run artifacts are not releases: they expire, and they are only visible
to people with repo access. Use a tag when you want something players
can download.

Releases and the server deploy are independent: the server builds from
its own clone and does not consume release assets. Tagging is purely how
players get the file.

## Alternative profiles (not currently deployed)

| | Create Aeronautics |
|---|---|
| Version | 1.21.1 |
| Loader | NeoForge |
| Contents | Create Aeronautics modpack (requires Create, Sable) |
| JVM heap | 6-8 GB |

Switching means resizing the instance (see `../aws/NOTES.md`) and
re-checking datapack compatibility -- Matcha Flavoured and Path
Generator are pinned to 26.2 because that is what exists, not because of
any relation to 1.21.1. `build.py` currently emits Fabric dependencies
only; a NeoForge profile needs its dependency key added.

### Seasons and Terralith

Serene Seasons sorts biomes with four tags that list only vanilla
biomes. `server-overrides/world/datapacks/z-seasons-terralith/` adds
Terralith's biomes to them. The tag files are generated from
`tools/seasons_terralith.py`, which holds the reason for every biome.
`SEASONS_TERRALITH.md` covers what each list does, what was left out
and what is untested. Run `python3 tools/seasons_terralith.py --audit`
after a Terralith update to see every biome and what it gets.

### Saplings and Terralith

`server-overrides/world/datapacks/z-treeplacer-terralith/` maps sapling
growth to Terralith's configured trees. In a Terralith biome with trees,
all recognized single sapling types can grow one of that biome's tree
variants **of the same wood species**; a spruce sapling always grows a
spruce-trunk tree, for example. Related biomes can share variants of that
same species, while 2x2 sapling growth similarly uses available giant
trees of the matching wood. This lets a player-planted sapling get a
thematically fitting variant without changing its wood type.
The Ice Marsh mangrove variants are also available to propagules in
Orchid Swamp, Warm River, the tropical/amethyst rainforests, and the
desert oases/Lush Desert.

For selected tree-less Terralith biomes, `tools/treeplacer_terralith.py`
uses a manually chosen similar biome as the palette source. Unmapped
Terralith cases and all vanilla biomes retain vanilla growth. Rebuild the
datapack after changing its source mappings with:

```sh
python3 minecraft/tools/treeplacer_terralith.py
python3 minecraft/build.py
```

The palette choices are pragmatic rather than a simulation of every
species' climate limits. A selected tree that cannot fit still does not
grow; Treeplacer does not then retry vanilla growth.
