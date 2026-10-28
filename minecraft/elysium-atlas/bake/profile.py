"""Scale profiles: every number that depends on the world's scale, in one JSON file per build.

Units: keys ending _m are real metres, _blocks are blocks, plain counts are cells. A level's cell size is given in
metres and becomes blocks through metres_per_block, so a profile change rescales every level at once.

  dev-globe   150 m/block, whole globe (the local dev world; reproduces slice-9)
  dev-window  15 m/block, a small box for in-game tuning at server scale
  server-*    15 m/block, baked by continent (later)

The profile is picked with --profile NAME or ELYSIUM_PROFILE (default dev-globe). atlas.json carries its name and
hash; the mod refuses a world generated with a different hash.
"""
import hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "profiles")


def name_from_argv(argv=None):
    """Profile name from --profile NAME (removed from argv, so each script's own parser never sees it) or ELYSIUM_PROFILE."""
    import sys
    argv = sys.argv if argv is None else argv
    for i, a in enumerate(argv):
        if a == "--profile" and i + 1 < len(argv):
            name = argv[i + 1]; del argv[i:i + 2]; return name
        if a.startswith("--profile="):
            del argv[i]; return a.split("=", 1)[1]
    return os.environ.get("ELYSIUM_PROFILE", "dev-globe")


def load(name=None):
    name = name or name_from_argv()
    p = json.load(open(os.path.join(DIR, f"{name}.json")))
    if p.get("name") != name: raise SystemExit(f"profile {name}: name field says {p.get('name')}")
    mpb = p["metres_per_block"]
    for lv in p["levels"]:
        c = lv["cell_m"] / mpb
        if abs(c - round(c)) > 1e-9: raise SystemExit(f"profile {name}: level {lv['name']} cell {lv['cell_m']} m is not whole blocks")
        lv["cell"] = int(round(c))
    p["hash"] = digest(p)
    return p


def digest(p):
    """Hash of everything that shapes the terrain (derived keys and notes excluded)."""
    core = {k: v for k, v in p.items() if k not in ("hash", "notes")}
    core["levels"] = [{k: v for k, v in lv.items() if k != "cell"} for lv in p["levels"]]
    return hashlib.sha256(json.dumps(core, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
