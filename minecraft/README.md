# Minecraft

## Current server

| | |
|---|---|
| Version | 26.2 (vanilla) |
| Loader | none |
| Port | 25565/TCP |

## Datapacks

See `datapacks/`. `datapacks.yaml` is the source of truth (pinned URLs +
checksums). `datapacks/install.sh` is a Pterodactyl egg install script --
paste it into the egg's Install Script field and it runs automatically
inside the container on every install/reinstall. `MANIFEST.md` describes
what each datapack does.

## Modded profile (not currently deployed)

| | |
|---|---|
| Version | 1.21.1 |
| Loader | NeoForge |
| Modpack | Create Aeronautics (requires Create, Sable) |
| JVM heap | 6-8 GB |

Documented for reference; switching to this profile requires re-checking
datapack compatibility against 1.21.1 and resizing the instance (see
`../aws/NOTES.md`).
