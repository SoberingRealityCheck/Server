# Datapacks

| Name | Source | Purpose |
|---|---|---|
| Matcha Flavoured | https://modrinth.com/project/QI0EmgZ1 | Discourages mob-farm/grinding gameplay; rewards exploration, fishing, cooking |
| Path Generator Datapack | https://modrinth.com/datapack/path-generator-datapack | Auto-generates paths on tiles crossed repeatedly by foot or mount |

Both are pure vanilla-mechanic datapacks with no mod dependencies.

Pinned versions, download URLs, and checksums: `datapacks.yaml`.

Install: `install.sh` is a Pterodactyl egg install script, not a script
you run directly. Paste its contents into the egg's Install Script field
(Panel Admin -> Nests -> Eggs -> Configuration) and it runs automatically,
inside the container, on every server install/reinstall -- see the
header comment in `install.sh` for details. Manual fallback: download
each `url` from `datapacks.yaml` and place it in `world/datapacks/` via
the Panel's file manager.
