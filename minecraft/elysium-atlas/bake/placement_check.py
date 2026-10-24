"""Check scored placement against RESOLVE (rule 6), on a 10' preview grid or on a baked atlas.

usage: python3 placement_check.py preview EXP_DIR ATLAS_DIR [--png OUT.png]   10' grid, climate at WorldClim elevation
       python3 placement_check.py atlas ATLAS_DIR                            the baked L0 biome bytes
Prints, per RESOLVE biome type, the share of cells whose biome is in the wrong family, the top biomes, and the
picks at a list of test places. Exits 1 when a type's wrong-family share is above LIMIT.
"""
import gzip, json, math, os, struct, sys
import numpy as np
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from placement import Placement, Niche, FORMATION_COVER, Wetland
from bake_atlas import ee_fwd, MPB

RESOLVE = {1: "Tropical moist broadleaf", 2: "Tropical dry broadleaf", 3: "Tropical conifer", 4: "Temperate broadleaf/mixed",
           5: "Temperate conifer", 6: "Boreal", 7: "Tropical grassland/savanna", 8: "Temperate grassland/savanna",
           9: "Flooded grassland", 10: "Montane grassland", 11: "Tundra", 12: "Mediterranean", 13: "Desert/xeric", 14: "Mangrove"}
OK = {1: "forest woodland wetland", 2: "forest woodland", 3: "forest woodland", 4: "forest woodland wetland", 5: "forest woodland mountain",
      6: "forest woodland wetland tundra", 7: "woodland grass shrub", 8: "grass woodland shrub", 9: "wetland grass", 10: "grass shrub tundra mountain woodland",
      11: "tundra mountain", 12: "woodland shrub forest", 13: "desert shrub grass mountain", 14: "wetland forest"}
LIMIT = 0.30
NO_LIMIT = {9}     # flooded grasslands (Sudd, Pantanal) need seasonal flooding the water mask does not model
PLACES = {"Hill Country": (-99.1, 30.1), "Cross Timbers": (-97.8, 33.3), "Kansas prairie": (-96.6, 38.9), "Mississippi bottoms": (-90.9, 33.4),
          "Louisiana bayou": (-91.3, 30.1), "Florida": (-81.5, 28.0), "Tibet": (88.0, 32.5), "Altiplano": (-68.0, -18.0), "Alps": (8.0, 46.5),
          "Paris": (2.4, 48.8), "Scotland": (-4.5, 57.0), "Siberia": (105.0, 62.0), "Mongolia": (104.0, 46.5), "Sahara": (10.0, 24.0),
          "Amazon": (-62.0, -4.0), "Congo": (22.0, 0.0), "Borneo": (114.0, 1.0), "Serengeti": (35.0, -2.5), "Outback": (134.0, -24.0),
          "California": (-121.0, 37.5), "Pampas": (-61.0, -35.0), "Patagonia": (-69.0, -45.0), "Canadian shield": (-80.0, 52.0),
          "Andalusia": (-5.0, 37.5), "Japan": (138.0, 36.5), "Ukraine": (32.0, 49.0), "Redwoods": (-123.9, 41.3), "Iceland": (-19.0, 64.8)}

def family(n):
    if n.wet: return "wetland"
    if n.landform in ("peak", "cliff", "mountain") and n.cover < 0.3: return "mountain"
    if n.cover >= 0.55 and n.landform not in ("peak", "cliff"): return "forest"      # snowy forests are forest
    if n.snow or (n.theta < 0.2 and n.cover < 0.4): return "tundra"
    if (n.mu < 0.25 and n.cover < 0.25) or (n.tags & {"c:is_desert", "c:is_sandy", "c:is_badlands"} and n.cover < 0.45): return "desert"
    if n.cover >= 0.55: return "forest"
    if n.cover >= 0.2: return "woodland"
    return "grass" if n.mu >= 0.45 else "shrub"

def load_regions(atlas):
    a = json.load(open(os.path.join(atlas, "atlas.json"))); names = a["regions"]["names"]
    raw = gzip.open(os.path.join(atlas, a["regions"]["file"])).read()
    _, cell, i0, j0, w, h = struct.unpack("<HHiiii", raw[4:24]); u = np.frombuffer(raw[24:], "<u2").reshape(h, w)
    eco = json.load(open(os.path.join(HERE, "..", "variants", "data", "ecoregions.json")))
    bn = np.zeros(len(names) + 1, np.int16)
    for k, nm in enumerate(names):
        e = eco.get(nm.split(":")[1].split("/")[0]) if nm.startswith("eco:") else None
        bn[k + 1] = e["biome_num"] if e else 0
    return u, bn, cell, i0, j0

def report(pick_ids, rbn, weight, places):
    pl = Placement.__new__(Placement)
    fam = {}; fails = []
    print(f"{'RESOLVE type':28s} {'wrong':>6s}  top biomes")
    for t, name in RESOLVE.items():
        m = rbn == t; tot = float(weight[m].sum())
        if tot == 0: continue
        ids, inv = np.unique(pick_ids[m], return_inverse=True); w = np.bincount(inv, weights=weight[m]) / tot
        wrong = sum(wi for i, wi in zip(ids, w) if FAM[i] not in OK[t].split())
        top = ", ".join(f"{NAMES[i].split(':')[1]} {100 * wi:.0f}%" for wi, i in sorted(zip(w, ids), reverse=True)[:5])
        bad = ", ".join(f"{NAMES[i].split(':')[1]}({FAM[i]}) {100 * wi:.0f}%" for wi, i in sorted(zip(w, ids), reverse=True) if FAM[i] not in OK[t].split())
        print(f"{name:28s} {100 * wrong:5.1f}%  {top}\n{'':36s}wrong: {bad[:150]}")
        if wrong > LIMIT and t not in NO_LIMIT: fails.append(name)
    for k, v in places.items(): print(f"  {k:20s} {v}")
    return fails

def main():
    global FAM, NAMES
    mode = sys.argv[1]
    P = Placement(os.path.join(HERE, "data", "biome_traits.json"))
    if mode == "preview":
        exp, atlas = sys.argv[2:4]
        g = np.load(os.path.join(exp, "globe", "biome_v2_global_10m.npz")); c10 = np.load(os.path.join(exp, "globe", "climate_globe_10m.npz"))
        land = c10["land"] & (g["biome"] != 255); lat = c10["lat"]; lon = c10["lon"]
        LON, LAT = np.meshgrid(lon, lat); z = g["elev_wc"].astype(np.float32)
        relief = ndi.maximum_filter(z, 3) - ndi.minimum_filter(z, 3)
        relief = relief * 0.6        # 10' cells (~18 km window) see more relief than the atlas's ~14 km window
        x, y = ee_fwd(LON, LAT); xb, zb = x / MPB, -y / MPB
        wet = Wetland(os.path.join(exp, "atlas", "hydro_v2_5km_warm.npz"), ee_fwd).mask(xb, zb, MPB, relief, z, g["MI"].astype(np.float32), x, y)
        coast = land & ndi.binary_dilation(~land, iterations=1)
        meta = json.load(open(os.path.join(exp, "globe", "biome_v2_global.json"))); form = [b["id"] for b in meta["biomes"]]
        fc = np.array([FORMATION_COVER[f] for f in form] + [0.0] * (256 - len(form)), np.float32)[g["biome"]]
        ct = P.cell_terms(g["MAT"].astype(np.float32), g["Thot"].astype(np.float32), g["Tcold"].astype(np.float32),
                          g["MI"].astype(np.float32), g["dry_months"], fc, g["med"])
        c = {k: v[land] for k, v in ct.items()}
        c.update({"relief": relief[land], "zr": z[land], "wet": wet[land], "coast": coast[land], "realm": g["realm"][land], "xm": x[land], "ym": y[land]})
        arg = P.pick(c)
        u, bn, cell, i0, j0 = load_regions(atlas)
        ii = np.clip((xb[land] / cell).astype(int) - i0, 0, u.shape[1] - 1); jj = np.clip((zb[land] / cell).astype(int) - j0, 0, u.shape[0] - 1)
        rbn = bn[u[jj, ii]]; weight = np.cos(np.radians(LAT[land]))
        NAMES = P.ids; FAM = [family(n) for n in P.niches]
        places = {}
        for k, (lo, la) in PLACES.items():
            r = int(round((90 - la) * 6 - 0.5)); cc = int(round((lo + 180) * 6 - 0.5)); idx = np.flatnonzero(land.ravel() == 1)
            pos = np.searchsorted(idx, r * land.shape[1] + cc)
            if pos < len(idx) and idx[pos] == r * land.shape[1] + cc:
                cs = {kk: (vv[pos:pos + 1] if isinstance(vv, np.ndarray) else vv) for kk, vv in c.items()}
                if os.environ.get("EXPLAIN") == k: print(k, {kk: vv for kk, vv in cs.items()})
                sc = sorted((float(P.scores(n, cs)[0]), n.id.split(":")[1]) for n in P.niches)[:4]
                places[k] = f"MAT {g['MAT'][r, cc]:.0f} MI {g['MI'][r, cc]:.2f} rel {relief[r, cc]:.0f} wet {wet[r, cc]} -> " + ", ".join(f"{b} {s:.1f}" for s, b in sc)
            else: places[k] = "sea"
        ids_used = np.unique(arg); print(len(ids_used), "biomes used")
        share = np.bincount(arg, weights=weight, minlength=len(P.ids)) / weight.sum()
        print("top:", ", ".join(f"{P.ids[i].split(':')[1]} {100 * share[i]:.1f}" for i in np.argsort(-share)[:25]))
        fails = report(arg, rbn, weight, places)
        if "--png" in sys.argv:
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            FC = {"forest": (0.13, 0.42, 0.18), "woodland": (0.45, 0.62, 0.25), "grass": (0.72, 0.82, 0.42), "shrub": (0.80, 0.72, 0.45),
                  "desert": (0.93, 0.85, 0.6), "tundra": (0.9, 0.93, 0.97), "mountain": (0.55, 0.52, 0.5), "wetland": (0.2, 0.55, 0.6)}
            col = np.array([FC[f] for f in FAM]); img = np.ones(land.shape + (3,)) * 0.97; img[land] = col[arg]
            # tint by biome so neighbours inside a family stay visible
            rng = np.random.default_rng(3); jit = rng.uniform(-0.08, 0.08, (len(FAM), 3)); img[land] = np.clip(img[land] + jit[arg], 0, 1)
            out = sys.argv[sys.argv.index("--png") + 1]
            plt.imsave(out, img)
            plt.imsave(out.replace(".png", "_na.png"), np.kron(img[180:420, 300:720], np.ones((3, 3, 1))))
        sys.exit(1 if fails else 0)

def check_atlas(atlas):
    """Rule 6 on a baked atlas: L0 biome bytes against the region layer (same 32-block grid)."""
    global FAM, NAMES
    a = json.load(open(os.path.join(atlas, "atlas.json"))); pal = a["biome_palette"]
    P = Placement(os.path.join(HERE, "data", "biome_traits.json"))
    tr = json.load(open(os.path.join(HERE, "data", "biome_traits.json")))
    niche = {k: Niche(k, v) for k, v in tr.items()}
    NAMES = pal; FAM = [family(niche[k]) if k in niche else "water" for k in pal]
    u, bn, cell, i0, j0 = load_regions(atlas)
    picks, rbns, wts = [], [], []
    d = os.path.join(atlas, "L0")
    for f in sorted(os.listdir(d)):
        tx, tz = map(int, f.split(".")[0].split("_")); raw = gzip.open(os.path.join(d, f)).read(); T = struct.unpack("<H", raw[6:8])[0]
        b = np.frombuffer(raw[8 + 3 * T * T:], np.uint8).reshape(T, T)
        jj, ii = np.mgrid[0:T, 0:T]; gi = tx * T + ii - i0; gj = tz * T + jj - j0
        ok = (b != 255) & (gi >= 0) & (gj >= 0) & (gi < u.shape[1]) & (gj < u.shape[0])
        r = bn[u[gj[ok], gi[ok]]]; picks.append(b[ok]); rbns.append(r); wts.append(np.ones(r.shape, np.float32))
    pick = np.concatenate(picks).astype(np.int32); rbn = np.concatenate(rbns); w = np.concatenate(wts)
    land = np.array([f != "water" for f in FAM])[pick]
    share = np.bincount(pick[land], minlength=len(pal)) / land.sum()
    print(int((share > 0).sum()), "land biomes used; top:", ", ".join(f"{pal[i].split(':')[1]} {100 * share[i]:.1f}" for i in np.argsort(-share)[:20]))
    return report(pick[land], rbn[land], w[land], {})

if __name__ == "__main__":
    if sys.argv[1] == "atlas": sys.exit(1 if check_atlas(sys.argv[2]) else 0)
    main()
