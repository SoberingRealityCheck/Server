# Server

Self-hosted game server infrastructure: an AWS EC2 host running
[Pterodactyl](https://pterodactyl.io) (Panel + Wings) via Docker Compose.

## Layout

```
Server/
├── docker-compose.yml   # Panel + database + cache + Wings
├── .env.example          # copy to .env and fill in secrets
├── aws/
│   └── NOTES.md          # instance spec, security group, DNS
├── wings/
│   ├── config.example.yml # node config template
│   └── README.md          # Wings setup and known gotchas
└── minecraft/
    ├── README.md          # game-specific config
    ├── egg-fabric.json    # importable Pterodactyl egg
    ├── datapacks/
    │   ├── datapacks.yaml # pinned datapack sources
    │   ├── install.sh     # automated datapack installer
    │   └── MANIFEST.md    # datapack descriptions
    └── mods/
        ├── server/        # egg-installed automatically
        │   ├── mods.yaml
        │   ├── install.sh
        │   └── MODLIST.md
        └── client/        # manual install, docs only
            ├── mods.yaml
            └── MODLIST.md
```

Each game gets its own top-level directory alongside `minecraft/`; the
root of the repo stays host-level and game-agnostic.

## Architecture

Panel and Wings run on a single host via Docker Compose. Wings mounts the
host's Docker socket (not Docker-in-Docker) to manage per-server game
containers directly. No IaC layer -- infrastructure is provisioned
manually per `aws/NOTES.md`.

## Requirements

- Docker Engine + the Compose plugin
- An AWS EC2 instance (spec in `aws/NOTES.md`)
- A DNS provider supporting A and SRV records

## Setup

1. Provision the EC2 instance and security group per `aws/NOTES.md`.
2. Point DNS at the instance (see `aws/NOTES.md`).
3. Install Docker on the instance and copy this repo to it.
4. Copy `.env.example` to `.env` and fill in real values.
5. `docker compose up -d`
6. Complete Panel's first-run setup and register a Node pointing Wings at
   `localhost`.
7. Configure Wings: copy `wings/config.example.yml` to
   `data/wings/etc/config.yml` and fill in the node credentials from
   Panel -- see `wings/README.md`.
8. Create game servers through the Panel -- see per-game docs (e.g.
   `minecraft/README.md`).

## Backups and whitelist

Both configured per-server through the Panel; no additional tooling
required.
