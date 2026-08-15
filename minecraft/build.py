#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Compile pack.yaml into dist/pack.mrpack (a Modrinth modpack).

The .mrpack format is a zip containing modrinth.index.json -- a manifest
listing every file with its download URL, hashes, size, and which side
(client/server) it belongs on -- plus an optional overrides/ directory of
files copied verbatim into the instance.

pack.yaml pins a URL and sha512 per entry, but the format also requires
sha1 and byte size, which can only be obtained from the artifact itself.
So this script downloads each file once, verifies the pinned sha512, and
derives the rest. Downloads are cached in .cache/ keyed by sha512, so
repeat builds are offline and instant.

A sha512 mismatch aborts the build. That is the point: a changed or
tampered artifact fails here rather than reaching the server.

Usage:
    ./build.py              # build dist/pack.mrpack + MODLIST.md
    ./build.py --check      # verify everything, write nothing
    ./build.py --offline    # fail rather than download anything

Run via `uv run --script build.py` (or just `./build.py`, uv's shebang
handles it) -- uv installs PyYAML into an isolated env automatically,
no venv or pip install needed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PACK_FILE = HERE / "pack.yaml"
OVERRIDES_DIR = HERE / "overrides"
CACHE_DIR = HERE / ".cache"
DIST_DIR = HERE / "dist"
OUTPUT = DIST_DIR / "pack.mrpack"
MODLIST = HERE / "MODLIST.md"

FABRIC_META_LOADER = "https://meta.fabricmc.net/v2/versions/loader"
MODRINTH_API = "https://api.modrinth.com/v2"

# pack.yaml's `env` shorthand -> the modrinth.index.json env object.
# "unsupported" tells an installer to skip the file entirely on that
# side, which is how one manifest serves both server and clients.
ENV_MAP = {
    "both": {"client": "required", "server": "required"},
    "client": {"client": "required", "server": "unsupported"},
    "server": {"client": "unsupported", "server": "required"},
}


class BuildError(Exception):
    """Anything that should stop the build with a readable message."""


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "elysium-pack-build/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise BuildError(f"could not fetch {url}: {exc}") from exc


def resolve_loader_version(pinned: str, offline: bool) -> str:
    """Return the Fabric Loader version, resolving 'latest' if asked."""
    if pinned != "latest":
        return pinned
    if offline:
        raise BuildError(
            "loader_version is 'latest' but --offline was given. "
            "Pin an explicit version in pack.yaml."
        )
    data = json.loads(fetch(FABRIC_META_LOADER))
    stable = [v["version"] for v in data if v.get("stable")]
    if not stable:
        raise BuildError("no stable Fabric Loader version found upstream")
    resolved = stable[0]
    print(f"  loader_version: latest -> {resolved}  (pin this in pack.yaml)")
    return resolved


def cached_bytes(entry: dict, offline: bool) -> bytes:
    """Return the artifact's bytes, downloading only if not already cached.

    Cache keyed by sha512 rather than filename: if a pinned hash changes,
    that is a different artifact and gets a different cache slot, so a
    stale download can never masquerade as the new one.
    """
    expected = entry["sha512"].lower()
    slot = CACHE_DIR / expected[:16] / entry["file"]

    if slot.exists():
        blob = slot.read_bytes()
        if hashlib.sha512(blob).hexdigest() == expected:
            return blob
        slot.unlink()  # corrupt cache entry, refetch below

    if offline:
        raise BuildError(f"{entry['name']}: not cached and --offline was given")

    print(f"  downloading {entry['name']}")
    blob = fetch(entry["url"])

    actual = hashlib.sha512(blob).hexdigest()
    if actual != expected:
        raise BuildError(
            f"{entry['name']}: sha512 mismatch\n"
            f"    expected {expected}\n"
            f"    actual   {actual}\n"
            f"    url      {entry['url']}\n"
            "  The upstream artifact changed. Verify the new file on "
            "Modrinth before updating the hash in pack.yaml."
        )

    slot.parent.mkdir(parents=True, exist_ok=True)
    slot.write_bytes(blob)
    return blob


def build_file_entry(entry: dict, dest_dir: str, env: str, offline: bool) -> dict:
    blob = cached_bytes(entry, offline)
    return {
        "path": f"{dest_dir}/{entry['file']}",
        "hashes": {
            "sha1": hashlib.sha1(blob).hexdigest(),
            "sha512": entry["sha512"].lower(),
        },
        "env": ENV_MAP[env],
        "downloads": [entry["url"]],
        "fileSize": len(blob),
    }


def validate(pack: dict) -> None:
    """Catch manifest mistakes before any network work happens."""
    for key in ("name", "version", "minecraft", "loader", "loader_version"):
        if not pack.get(key):
            raise BuildError(f"pack.yaml is missing required key: {key}")

    if pack["loader"] != "fabric":
        raise BuildError(
            f"loader is {pack['loader']!r}; this script only emits Fabric "
            "dependencies. Extend DEPENDENCY_KEY below to support others."
        )

    seen: dict[str, str] = {}
    for entry in pack.get("mods", []):
        for key in ("name", "file", "url", "sha512"):
            if not entry.get(key):
                raise BuildError(f"mod entry {entry.get('name', '?')} missing {key}")
        if entry.get("env") not in ENV_MAP:
            raise BuildError(
                f"{entry['name']}: env must be one of {sorted(ENV_MAP)}, "
                f"got {entry.get('env')!r}"
            )
        if entry["file"] in seen:
            raise BuildError(
                f"duplicate filename {entry['file']} "
                f"({seen[entry['file']]} and {entry['name']})"
            )
        seen[entry["file"]] = entry["name"]

    for entry in pack.get("datapacks", []):
        for key in ("name", "file", "url", "sha512"):
            if not entry.get(key):
                raise BuildError(f"datapack {entry.get('name', '?')} missing {key}")


def build_index(pack: dict, offline: bool) -> dict:
    files = []

    for entry in pack.get("mods", []):
        files.append(build_file_entry(entry, "mods", entry["env"], offline))

    for entry in pack.get("datapacks", []):
        files.append(build_file_entry(entry, "world/datapacks", "server", offline))

    return {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": pack["version"],
        "name": pack["name"],
        "summary": " ".join(pack.get("summary", "").split()),
        "files": files,
        "dependencies": {
            "minecraft": pack["minecraft"],
            "fabric-loader": pack["loader_version"],
        },
    }


def write_mrpack(index: dict) -> None:
    DIST_DIR.mkdir(exist_ok=True)
    if OUTPUT.exists():
        OUTPUT.unlink()

    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("modrinth.index.json", json.dumps(index, indent=2))

        if OVERRIDES_DIR.is_dir():
            for path in sorted(OVERRIDES_DIR.rglob("*")):
                if path.is_file() and path.name != ".gitkeep":
                    zf.write(path, f"overrides/{path.relative_to(OVERRIDES_DIR)}")


def write_modlist(pack: dict, index: dict) -> None:
    """Regenerate the human-readable list. Never edit MODLIST.md by hand --
    it is derived from pack.yaml and overwritten on every build."""
    side = {"both": "client + server", "client": "client only", "server": "server only"}
    lines = [
        f"# {pack['name']} -- contents",
        "",
        "<!-- GENERATED by build.py from pack.yaml. Do not edit by hand. -->",
        "",
        f"Minecraft {pack['minecraft']} / Fabric Loader {pack['loader_version']}",
        f"Pack version {pack['version']}",
        "",
        "## Mods",
        "",
        "| Mod | Side | Why |",
        "|---|---|---|",
    ]
    for entry in pack.get("mods", []):
        reason = " ".join(entry.get("reason", "").split())
        lines.append(f"| {entry['name']} | {side[entry['env']]} | {reason} |")

    if pack.get("datapacks"):
        lines += ["", "## Datapacks", "", "| Datapack | Side |", "|---|---|"]
        for entry in pack["datapacks"]:
            lines.append(f"| {entry['name']} | server only |")

    total = sum(f["fileSize"] for f in index["files"])
    lines += [
        "",
        f"{len(index['files'])} files, {total / 1_048_576:.1f} MiB total download.",
        "",
    ]
    MODLIST.write_text("\n".join(lines))


# --- Fabric dependency checking --------------------------------------
#
# Fabric resolves mod dependencies at launch and refuses to start if any
# are unsatisfiable. That check happens on the server, minutes after a
# build, and reports one failure at a time. Doing the same check here --
# against the real `fabric.mod.json` inside each jar, not a guess about
# what a version probably requires -- surfaces every conflict at once,
# before anything is deployed.

def parse_semver(v: str) -> tuple[int, ...] | None:
    """(major, minor, patch) or None if not parseable.

    Build metadata (`+26.2`) and prerelease tags (`-beta.1`) are dropped:
    semver orders on the numeric core, and mod versions here carry the
    Minecraft version as build metadata.
    """
    core = v.split("+", 1)[0].split("-", 1)[0].strip()
    parts = core.split(".")
    out = []
    for p in parts[:3]:
        if not p.isdigit():
            return None
        out.append(int(p))
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def satisfies_predicate(version: str, pred: str) -> bool | None:
    """Does `version` satisfy one Fabric predicate? None = unparseable."""
    pred = pred.strip()
    if pred in ("*", ""):
        return True

    for op in (">=", "<=", "!=", "==", ">", "<", "=", "^", "~"):
        if pred.startswith(op):
            target_raw = pred[len(op):].strip()
            break
    else:
        op, target_raw = "=", pred

    # x-ranges: 1.2.x / 1.2.* match any patch within 1.2
    if any(c in target_raw for c in "xX*"):
        prefix = target_raw.replace("*", "x").replace("X", "x").split(".x")[0]
        return version.split("+")[0].startswith(prefix)

    a, b = parse_semver(version), parse_semver(target_raw)
    if a is None or b is None:
        return None

    if op == ">=":
        return a >= b
    if op == "<=":
        return a <= b
    if op in (">",):
        return a > b
    if op in ("<",):
        return a < b
    if op == "!=":
        return a != b
    if op in ("=", "=="):
        return a == b
    if op == "^":
        # compatible-with: same major, at least the given version
        return a >= b and a[0] == b[0]
    if op == "~":
        # approximately: same major.minor, at least the given version
        return a >= b and a[:2] == b[:2]
    return None


def satisfies(version: str, spec) -> bool | None:
    """Fabric allows a string or a list (any-of). Space-separated
    predicates within one string are all-of."""
    if isinstance(spec, list):
        results = [satisfies(version, s) for s in spec]
        if any(r is True for r in results):
            return True
        return None if any(r is None for r in results) else False

    parts = str(spec).split()
    results = [satisfies_predicate(version, p) for p in parts]
    if any(r is False for r in results):
        return False
    return None if any(r is None for r in results) else True


def read_fabric_metadata(blob: bytes, out: dict, depends: dict) -> None:
    """Collect ids/versions and declared dependencies from a mod jar.

    Recurses into nested jars: Fabric API ships its modules as jars
    inside the outer jar, and mods routinely depend on those module ids
    directly. Skipping them would report a pile of false conflicts.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        return
    if "fabric.mod.json" not in zf.namelist():
        return
    try:
        meta = json.loads(zf.read("fabric.mod.json").decode("utf-8", "replace"))
    except (ValueError, KeyError):
        return

    mod_id, version = meta.get("id"), str(meta.get("version", ""))
    if mod_id:
        out[mod_id] = version
        for provided in meta.get("provides", []):
            out[provided] = version
        if meta.get("depends"):
            depends[mod_id] = meta["depends"]

    for nested in meta.get("jars", []):
        path = nested.get("file")
        if path and path in zf.namelist():
            read_fabric_metadata(zf.read(path), out, depends)


def check_dependencies(pack: dict, offline: bool) -> int:
    """Verify each side's mod set independently. Returns problem count.

    Client and server get different subsets, so a dependency satisfied on
    one side can be missing on the other -- exactly the failure mode
    where a `both` mod is marked `server` and clients crash at launch.
    """
    print("\nChecking Fabric dependencies against each jar's fabric.mod.json")
    problems = 0

    for side in ("server", "client"):
        wanted = [m for m in pack["mods"] if m["env"] in (side, "both")]
        available: dict[str, str] = {
            "minecraft": pack["minecraft"],
            "fabricloader": pack["loader_version"],
            "java": "21",
        }
        declared: dict[str, dict] = {}

        for entry in wanted:
            read_fabric_metadata(
                cached_bytes(entry, offline), available, declared
            )

        print(f"\n  [{side}] {len(wanted)} mods, "
              f"{len(available)} resolvable ids")

        for mod_id, deps in sorted(declared.items()):
            for dep_id, spec in deps.items():
                have = available.get(dep_id)
                if have is None:
                    print(f"    MISSING  {mod_id} needs {dep_id} {spec}")
                    problems += 1
                    continue
                ok = satisfies(have, spec)
                if ok is False:
                    print(f"    CONFLICT {mod_id} needs {dep_id} {spec}, "
                          f"have {have}")
                    problems += 1
                elif ok is None:
                    print(f"    unchecked {mod_id} needs {dep_id} {spec} "
                          f"(have {have}) -- could not parse range")

    if problems:
        print(f"\n{problems} dependency problem(s). Fabric will refuse to "
              f"start. Use --resolve <slug> to find newer builds.")
    else:
        print("\nAll declared dependencies satisfied on both sides.")
    return problems


def resolve_project(slug: str, mc_version: str, loader: str) -> str:
    """Print a ready-to-paste pack.yaml block for a Modrinth project.

    Prints rather than editing pack.yaml in place: PyYAML cannot
    round-trip a file without discarding its comments, and the reasoning
    recorded in those comments is worth more than the typing saved.
    """
    # Modrinth expects these filters as JSON arrays, percent-encoded.
    # Interpolating `["fabric"]` straight into the URL leaves the
    # brackets and quotes raw and the API answers 400.
    query = urllib.parse.urlencode({
        "loaders": json.dumps([loader]),
        "game_versions": json.dumps([mc_version]),
    })
    versions = json.loads(fetch(f"{MODRINTH_API}/project/{slug}/version?{query}"))
    if not versions:
        raise BuildError(
            f"no {loader} build of '{slug}' for Minecraft {mc_version}"
        )

    # The API returns newest first, but only among versions matching the
    # filters above -- so this is the newest compatible build, not merely
    # the newest build.
    v = versions[0]
    primary = next((f for f in v["files"] if f.get("primary")), v["files"][0])

    # Carry over name/env/reason from the entry already in pack.yaml, if
    # this project is one we track. Printing a default `env: server` and
    # trusting the reader to correct it is how a `both` mod silently
    # becomes server-only -- which breaks clients at launch, far from the
    # edit that caused it.
    existing = None
    project_id = v.get("project_id", "")
    if project_id:
        pack = yaml.safe_load(PACK_FILE.read_text())
        for entry in pack.get("mods", []):
            if f"/data/{project_id}/" in entry.get("url", ""):
                existing = entry
                break

    name = existing["name"] if existing else v.get("name", slug)
    env = existing["env"] if existing else "server"
    reason = " ".join(existing.get("reason", "").split()) if existing else ""

    print(f"  - name: \"{name}\"")
    print(f"    file: \"{primary['filename']}\"")
    print(f"    url: \"{primary['url']}\"")
    print(f"    sha512: \"{primary['hashes']['sha512']}\"")
    if existing:
        print(f"    env: {env}")
        print(f"    reason: \"{reason}\"" if reason else "    reason: \"\"")
    else:
        print("    env: server        # CHANGE ME: both | client | server")
        print("    reason: \"\"")
    print()
    if existing:
        print(f"# carried over env and reason from the existing "
              f"'{existing['name']}' entry", file=sys.stderr)
    print(f"# version {v['version_number']} ({v['version_type']}), "
          f"published {v['date_published'][:10]}", file=sys.stderr)

    required = [d for d in v.get("dependencies", [])
                if d.get("dependency_type") == "required"]
    if required:
        print("# required dependencies -- make sure pack.yaml satisfies these:",
              file=sys.stderr)
        for dep in required:
            pid = dep.get("project_id")
            try:
                proj = json.loads(fetch(f"{MODRINTH_API}/project/{pid}"))
                label = f"{proj.get('title', pid)} ({proj.get('slug', pid)})"
            except (BuildError, ValueError, KeyError, TypeError):
                # Purely an annotation -- a failed or malformed lookup
                # should degrade to the bare ID, never abort a resolve
                # that already produced a usable block.
                label = str(pid)
            print(f"#   - {label}", file=sys.stderr)
    return "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify manifest and hashes, write nothing")
    parser.add_argument("--offline", action="store_true",
                        help="use only cached artifacts; never download")
    parser.add_argument("--clean", action="store_true",
                        help="delete the download cache and exit")
    parser.add_argument("--resolve", metavar="SLUG",
                        help="print an up-to-date pack.yaml block for a "
                             "Modrinth project (e.g. --resolve fabric-api)")
    parser.add_argument("--check-deps", action="store_true",
                        help="verify Fabric mod dependencies per side and "
                             "exit; catches what Fabric would reject at "
                             "launch")
    args = parser.parse_args()

    if args.clean:
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        print(f"removed {CACHE_DIR}")
        return 0

    if args.resolve:
        try:
            pack = yaml.safe_load(PACK_FILE.read_text())
            resolve_project(args.resolve, pack["minecraft"], pack["loader"])
        except BuildError as exc:
            print(f"\nerror: {exc}", file=sys.stderr)
            return 1
        return 0

    try:
        pack = yaml.safe_load(PACK_FILE.read_text())
        validate(pack)

        print(f"Building {pack['name']} v{pack['version']}")
        pack["loader_version"] = resolve_loader_version(
            pack["loader_version"], args.offline
        )

        if args.check_deps:
            return 1 if check_dependencies(pack, args.offline) else 0

        index = build_index(pack, args.offline)

        if args.check:
            print(f"OK: {len(index['files'])} files verified, nothing written")
            return 0

        write_mrpack(index)
        write_modlist(pack, index)

    except BuildError as exc:
        # Flush first: stdout is block-buffered when piped, so without this
        # the error lands above the progress lines it should follow.
        sys.stdout.flush()
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for f in index["files"]:
        key = f"{f['env']['client']}/{f['env']['server']}"
        counts[key] = counts.get(key, 0) + 1

    print(f"\nwrote {OUTPUT.relative_to(HERE)} ({OUTPUT.stat().st_size:,} bytes)")
    print(f"wrote {MODLIST.relative_to(HERE)}")
    print(f"  {len(index['files'])} files total")
    for key, n in sorted(counts.items()):
        print(f"    {key}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
