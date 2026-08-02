# Minecraft

## Current server

| | |
|---|---|
| Version | 26.2 |
| Loader | Fabric |
| Port | 25565/TCP |

Fabric "realistic terrain" profile -- Terralith/Tectonic worldgen,
Distant Horizons LOD rendering, plus performance, QOL, and sound mods,
layered under the Matcha Flavoured and Path Generator datapacks. Full mod
lists, versions, and checksums: `mods/server/MODLIST.md` and
`mods/client/MODLIST.md`.

Requires a Fabric egg targeting 26.2 and meaningfully more RAM than a
vanilla-only server -- not yet benchmarked. The instance was originally
sized for vanilla + datapacks only; see `../aws/NOTES.md` for current
sizing and resize procedure before going live.

`egg-fabric.json` is a ready-to-import Pterodactyl egg (Panel Admin ->
Nests -> Import Egg) -- Fabric loader pinned to 26.2, plus this repo's
`mods/server/` and `datapacks/` installed automatically on every
install/reinstall. Fill in the `<github-user>/<repo>` placeholder in its
install script before importing.

## Mods

`mods/server/` is installed automatically via `install.sh`, a
Pterodactyl egg install script (same mechanism as the datapack
installer). `mods/client/` is manual-install only, for mods that only
affect the player's own rendering/UI and do nothing on a dedicated
server. Distant Horizons, JEI, and Jade appear in both -- they need a
copy on each side. See each folder's `MODLIST.md` for details.

## Datapacks

See `datapacks/`. `datapacks.yaml` is the source of truth (pinned URLs +
checksums). `datapacks/install.sh` is a Pterodactyl egg install script --
paste it into the egg's Install Script field and it runs automatically
inside the container on every install/reinstall. `MANIFEST.md` describes
what each datapack does.

## Alternative profiles (not currently deployed)

| | Create Aeronautics |
|---|---|
| Version | 1.21.1 |
| Loader | NeoForge |
| Contents | Create Aeronautics modpack (requires Create, Sable) |
| JVM heap | 6-8 GB |

Not active, and switching to it means re-sizing the instance again (see
`../aws/NOTES.md`) and re-checking datapack compatibility -- Matcha
Flavoured and Path Generator are pinned to 26.2 specifically because
that's what's available, not because of any relation to 1.21.1.
