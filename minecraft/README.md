# Minecraft

## Current server

| | |
|---|---|
| Version | 26.2 |
| Loader | Fabric |
| Port | 25565/TCP |
| Profile | Elysium Realistic Terrain |

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
./build.py            # writes dist/pack.mrpack and MODLIST.md
./build.py --check    # verify hashes, write nothing
./build.py --offline  # build from cache, no network
./build.py --clean    # drop the download cache
```

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
3. `./build.py` -- this also regenerates `MODLIST.md`.
4. Commit both `pack.yaml` and `MODLIST.md`. CI fails if `MODLIST.md`
   is stale, so they stay in step.
5. Deploy: `docker compose up -d --force-recreate minecraft` from the
   repo root.
6. Release for players: `git tag v<version> && git push --tags`.

## Releases

`.github/workflows/pack.yml` builds the pack and attaches it to a GitHub
release whenever you push a `v*` tag. The tag must match `version` in
`pack.yaml` -- the workflow refuses otherwise, since a pack whose
internal version disagrees with its download URL makes "which version am
I running?" unanswerable.

On ordinary pushes and PRs the same workflow verifies every pinned
sha512 and checks that `MODLIST.md` is current, without publishing
anything. Downloaded artifacts are cached between runs, keyed by
`pack.yaml`'s contents -- change a pinned hash and the cache key changes
with it, so a stale jar can never be reused for a new pin.

### Building without a release

To build the pack on demand -- to sanity-check a `pack.yaml` edit, or
just to get a `.mrpack` without tagging -- use **Actions → pack → Run
workflow** on GitHub. The built pack is attached to the run as an
artifact named `pack.mrpack`, downloadable from the run summary page for
14 days.

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
