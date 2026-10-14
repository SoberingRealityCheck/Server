#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Make a singleplayer test instance that plays like the server.

    tools/local_instance.py install INSTANCE_DIR
    tools/local_instance.py world   INSTANCE_DIR WORLD_NAME
    tools/local_instance.py check   INSTANCE_DIR [WORLD_NAME] [--server-data DIR]
    tools/local_instance.py capture [--server-data DIR]

INSTANCE_DIR is the game folder of a launcher profile (the one with
mods/, config/, saves/). Make an empty Fabric 26.2 profile, then:

  1. install   every mod (client, both AND server), all configs, packs.
  2. launch once, create world WORLD_NAME, quit.
  3. world     datapacks + a pack that sets difficulty and gamerules.
  4. check     prints every value that differs from the repo / server.

Why a plain client install is not enough:
  - Server-only mods are not in the client set, so singleplayer would
    run without them. install adds them.
  - Two of them (seasonal-spawns, RoadWeaver) say "environment":
    "server" in fabric.mod.json. Fabric will not load that in singleplayer
    even with the jar present. HACK: install rewrites that one field in
    the instance's copy. The jars in the pack are not touched.
  - server-overrides/ (configs, datapacks) never reaches a client.
  - Gamerules and difficulty live in the world, not in any config file.
    They are not in the repo, so world-rules.json records them. Re-take
    it from the server with `capture`.

Dishonest on purpose: this talks to disk and the network. The compare
functions at the top are pure and are what `check` is made of.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # minecraft/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tools"))
import build  # noqa: E402  (pack.yaml loader, hash-checked download cache)
import nbt  # noqa: E402

RULES_FILE = HERE / "world-rules.json"
MANIFEST = ".elysium-parity.json"  # which files install put in mods/
RULES_PACK = "z-elysium-rules"  # "z-" so its load function runs last


# ---------------------------------------------------------------- pure

def parse_config(name: str, text: str):
    """Config text -> plain value, so '0.20' and '0.2' compare equal.

    .rules and anything unknown are lists of non-comment lines.
    """
    if name.endswith((".json", ".json5")):
        # Tectonic writes whole-line // comments. HACK: drop those lines only.
        # A // inside a string value on its own line would break this.
        return json.loads("\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("//")))
    if name.endswith(".toml"):
        return tomllib.loads(text)
    if name.endswith(".properties"):
        out = {}
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "!")) and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
        return out
    return [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]


def differences(want, got, path=""):
    """Every place `got` fails to match `want`. Empty list = match.

    Dicts are compared as a subset: keys only in `got` are fine. Mods
    rewrite their config on boot and add every default, and the repo
    file only lists what we chose. Lists must match exactly.
    """
    if isinstance(want, dict) and isinstance(got, dict):
        out = []
        for k, v in want.items():
            if k not in got:
                out.append(f"{path}{k}: missing (want {v!r})")
            else:
                out += differences(v, got[k], f"{path}{k}.")
        return out
    if isinstance(want, (int, float)) and isinstance(got, (int, float)) and want == got:
        return []
    if want != got:
        return [f"{path.rstrip('.') or '(file)'}: want {want!r}, got {got!r}"]
    return []


def rules_pack_files(rules: dict) -> dict[str, str]:
    """The datapack that sets difficulty + gamerules. path -> text.

    HACK: the load function runs on every world load and /reload, so a
    gamerule changed by hand in the test world snaps back. For a parity
    world that is the point. Delete the pack to play freely.
    """
    lines = [f"difficulty {rules['difficulty']}"]
    for name, value in sorted(rules["gamerules"].items()):
        lines.append(f"gamerule {name} {str(value).lower() if isinstance(value, bool) else value}")
    return {
        "pack.mcmeta": json.dumps(
            {"pack": {"description": "Elysium: server gamerules + difficulty",
                      "min_format": 88, "max_format": 107.1}}, indent=2),
        "data/elysium_rules/function/apply.mcfunction": "\n".join(lines) + "\n",
        "data/minecraft/tags/function/load.json": json.dumps(
            {"values": ["elysium_rules:apply"]}, indent=2),
    }


def rules_from_nbt(level: dict, game_rules: dict) -> dict:
    """level.dat + game_rules.dat contents -> world-rules.json shape.

    Rules come back from NBT as 0/1 ints, so a boolean rule and a
    number rule look alike. Fine: `gamerule x 1` is read as true.
    """
    return {
        "difficulty": level["difficulty_settings"]["difficulty"],
        "gamerules": dict(sorted(game_rules["data"].items())),
    }


# ------------------------------------------------------------- helpers

def find_server_data(arg: str | None) -> Path | None:
    """data/ of the local test server. Gitignored, so it lives in the
    main checkout, not in a worktree. Ask git where that is."""
    if arg:
        return Path(arg)
    for root in (HERE.parent, Path(subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=HERE,
            capture_output=True, text=True).stdout.strip()).resolve().parent):
        if (root / "data" / "world").is_dir():
            return root / "data"
    return None


def read_world_rules(server_data: Path) -> dict:
    world = server_data / "world"
    level = nbt.load(world / "level.dat")["Data"]
    rules = nbt.load(world / "data/minecraft/game_rules.dat")
    return rules_from_nbt(level, rules)


def patched_environment(blob: bytes) -> bytes | None:
    """Jar bytes with fabric.mod.json "environment" set to "*", or None
    if the jar was not server-only."""
    import io
    src = zipfile.ZipFile(io.BytesIO(blob))
    meta = json.loads(src.read("fabric.mod.json"), strict=False)
    if meta.get("environment") != "server":
        return None
    meta["environment"] = "*"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = json.dumps(meta, indent=2).encode() if info.filename == "fabric.mod.json" else src.read(info)
            dst.writestr(info, data)
    return out.getvalue()


def all_jars(pack: dict) -> list[tuple[str, bytes]]:
    """Every mod the pack ships, whatever side it is for."""
    jars = []
    for entry in pack["mods"]:
        if "local_file" in entry:
            continue  # lives in overrides/mods, copied with the overrides
        jars.append((entry["file"], build.cached_bytes(entry, offline=False)))
    for src in (build.OVERRIDES_DIR, build.CLIENT_OVERRIDES_DIR, build.SERVER_OVERRIDES_DIR):
        for p in sorted((src / "mods").glob("*.jar")) if (src / "mods").is_dir() else []:
            jars.append((p.name, p.read_bytes()))
    for _prefix, name, blob in build.local_mod_jars():
        jars.append((name, blob))
    return jars


def copy_tree(src: Path, dst: Path, skip_top: tuple[str, ...] = ()) -> int:
    n = 0
    if not src.is_dir():
        return 0
    for p in sorted(src.rglob("*")):
        rel = p.relative_to(src)
        if not p.is_file() or p.name == ".gitkeep" or rel.parts[0] in skip_top:
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst / rel)
        n += 1
    return n


# ------------------------------------------------------------ commands

def cmd_install(inst: Path) -> int:
    pack = build.yaml.safe_load(build.PACK_FILE.read_text())
    mods = inst / "mods"
    mods.mkdir(parents=True, exist_ok=True)

    # remove what the last install put here, so a mod dropped from the
    # pack goes away. Jars we did not install (dev builds) are left alone.
    mf = inst / MANIFEST
    for name in json.loads(mf.read_text())["mods"] if mf.exists() else []:
        (mods / name).unlink(missing_ok=True)

    names = []
    for name, blob in all_jars(pack):
        fixed = patched_environment(blob)
        if fixed:
            print(f"  hack: {name} was server-only, now loads in singleplayer")
            blob = fixed
        (mods / name).write_bytes(blob)
        names.append(name)
    mf.write_text(json.dumps({"mods": names}, indent=2))
    print(f"mods: {len(names)} jars (client + both + server)")

    # configs: shared, then client, then server. Later wins. world/ is
    # per-save, handled by `world`. mods/ was done above.
    for d in (build.OVERRIDES_DIR, build.CLIENT_OVERRIDES_DIR, build.SERVER_OVERRIDES_DIR):
        n = copy_tree(d, inst, skip_top=("world", "mods"))
        print(f"{d.name}: {n} files")

    for kind in ("shaderpacks", "resourcepacks"):
        for entry in pack.get(kind, []):
            (inst / kind).mkdir(exist_ok=True)
            (inst / kind / entry["file"]).write_bytes(build.cached_bytes(entry, offline=False))
    for dp in pack.get("datapacks", []):
        rp = dp.get("resourcepack")
        if isinstance(rp, dict):  # server pushes this one, so we place it by hand
            (inst / "resourcepacks").mkdir(exist_ok=True)
            (inst / "resourcepacks" / rp["file"]).write_bytes(build.cached_bytes(rp, offline=False))
            print(f"resourcepack {rp['file']}: placed. Turn it on under Options -> Resource Packs "
                  "(the server would push it for you)")
    print("done. Next: launch once, create a world, quit, run `world`.")
    return 0


def cmd_world(inst: Path, name: str) -> int:
    save = inst / "saves" / name
    if not (save / "level.dat").exists():
        print(f"no world at {save}. Create it in game first, then quit.")
        return 1
    pack = build.yaml.safe_load(build.PACK_FILE.read_text())
    dps = save / "datapacks"
    dps.mkdir(exist_ok=True)
    for dp in pack.get("datapacks", []):
        (dps / dp["file"]).write_bytes(build.cached_bytes(dp, offline=False))
    n = copy_tree(build.SERVER_OVERRIDES_DIR / "world", save)
    print(f"datapacks: {len(pack.get('datapacks', []))} zips + {n} files from server-overrides/world")

    rules = json.loads(RULES_FILE.read_text())
    for rel, text in rules_pack_files(rules).items():
        p = dps / RULES_PACK / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    print(f"{RULES_PACK}: difficulty {rules['difficulty']} + {len(rules['gamerules'])} gamerules")
    print("Open the world once, then run `check`. A new pack may start disabled.")
    return 0


def cmd_capture(server_data: Path | None) -> int:
    if not server_data:
        print("no server data/ found. Pass --server-data DIR.")
        return 1
    rules = read_world_rules(server_data)
    RULES_FILE.write_text(json.dumps(rules, indent=2) + "\n")
    print(f"wrote {RULES_FILE.name}: difficulty {rules['difficulty']}, {len(rules['gamerules'])} gamerules")
    return 0


def cmd_check(inst: Path, name: str | None, server_data: Path | None) -> int:
    bad = 0

    def report(title: str, lines: list[str]):
        nonlocal bad
        print(f"{title}: " + ("ok" if not lines else f"{len(lines)} differ"))
        for ln in lines:
            print("   ", ln)
        bad += len(lines)

    # 1. mods: every jar the pack ships is in the instance, byte for byte
    # (except the environment hack)
    pack = build.yaml.safe_load(build.PACK_FILE.read_text())
    lines = []
    for jar, blob in all_jars(pack):
        p = inst / "mods" / jar
        want = patched_environment(blob) or blob
        if not p.exists():
            lines.append(f"{jar}: missing")
        elif p.read_bytes() != want:
            lines.append(f"{jar}: differs from the pack")
    report("mods", lines)

    # 2. config: what the repo sets must hold in the instance AND on
    # the server's data/ (which shows what the live mods settled on).
    targets = [("instance", inst)] + ([("server data", server_data)] if server_data else [])
    for label, root in targets:
        lines = []
        for d in (build.OVERRIDES_DIR, build.CLIENT_OVERRIDES_DIR, build.SERVER_OVERRIDES_DIR):
            if label == "server data" and d == build.CLIENT_OVERRIDES_DIR:
                continue
            for p in sorted((d / "config").rglob("*")) if (d / "config").is_dir() else []:
                if not p.is_file():
                    continue
                rel = p.relative_to(d)
                got = root / rel
                if not got.exists():
                    lines.append(f"{rel}: missing")
                    continue
                try:
                    lines += [f"{rel} {x}" for x in differences(
                        parse_config(p.name, p.read_text()), parse_config(p.name, got.read_text()))]
                except Exception as e:  # unparseable file: say so, do not guess
                    lines.append(f"{rel}: could not compare ({e})")
        report(f"config vs {label}", lines)

    # 3. world: datapacks, difficulty, gamerules
    if not name:
        print("world: skipped (give WORLD_NAME)")
        return 1 if bad else 0
    save = inst / "saves" / name
    if not (save / "level.dat").exists():
        print(f"world: no level.dat at {save}")
        return 1
    lvl = nbt.load(save / "level.dat")["Data"]
    rules = json.loads(RULES_FILE.read_text())

    lines = []
    got = rules_from_nbt(lvl, nbt.load(save / "data/minecraft/game_rules.dat"))
    if got["difficulty"] != rules["difficulty"]:
        lines.append(f"difficulty: want {rules['difficulty']}, got {got['difficulty']}")
    lines += differences(rules["gamerules"], got["gamerules"], "gamerule ")
    report("difficulty + gamerules vs world-rules.json", lines)

    if server_data:
        srv = nbt.load(server_data / "world/level.dat")["Data"]["DataPacks"]
        here = lvl["DataPacks"]
        lines = []
        for p in srv["Enabled"]:
            if p not in here["Enabled"]:
                lines.append(f"not enabled: {p}   -> /datapack enable \"{p}\"")
        for p in here["Enabled"]:
            if p not in srv["Enabled"] and p != f"file/{RULES_PACK}":
                lines.append(f"extra, server lacks it: {p}   -> /datapack disable \"{p}\"")
        report("enabled datapacks vs server", lines)

        # per-world server configs (Forge Config API Port *-server.toml)
        lines = []
        for p in sorted((server_data / "world/serverconfig").glob("*.toml")):
            if not (save / "serverconfig" / p.name).exists():
                lines.append(f"serverconfig/{p.name}: missing")
        report("world serverconfig vs server", lines)
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install").add_argument("instance")
    w = sub.add_parser("world")
    w.add_argument("instance")
    w.add_argument("name")
    c = sub.add_parser("check")
    c.add_argument("instance")
    c.add_argument("name", nargs="?")
    c.add_argument("--server-data")
    k = sub.add_parser("capture")
    k.add_argument("--server-data")
    a = ap.parse_args()

    try:
        if a.cmd == "install":
            return cmd_install(Path(a.instance))
        if a.cmd == "world":
            return cmd_world(Path(a.instance), a.name)
        if a.cmd == "capture":
            return cmd_capture(find_server_data(a.server_data))
        return cmd_check(Path(a.instance), a.name, find_server_data(a.server_data))
    except build.BuildError as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
