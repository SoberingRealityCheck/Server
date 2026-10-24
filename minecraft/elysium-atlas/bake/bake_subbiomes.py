"""Sub-biomes (level 3) for the atlas detail level: a post-pass over finished L1 tiles.

Each 4-block cell (one Minecraft biome quart, 600 m real) gets a sub-biome class from terrain and old-world
land use, then a biome ID from (class, group of the formation biome already in the cell). Runs after
bake_atlas.py and bake_water.py: it changes only L1 biome bytes and atlas.json (palette, version, metadata),
never heights or water.

Inputs: Terrarium z10 (same tile cache as bake_atlas.py) and ESA WorldCover 2021 v200 (public S3, read as
overviews with rasterio, cached as .npy). Rules follow the sb1 prototype (worldgen-experiments/subbiome).

Behind a TLS proxy set GDAL_CURL_CA_BUNDLE (GDAL ignores CURL_CA_BUNDLE).
Usage: python3 bake_subbiomes.py ATLAS_DIR TILE_CACHE WC_CACHE [--version slice-5] [--render OUT.png]
"""
import argparse, gzip, json, math, os, struct, sys, time
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake_atlas import ee_inv, terrarium, MPB, SEA_RISE

# ---- frozen parameters (changing any changes biomes: bump the atlas version)
LEG = 5            # land-use fractions smoothed over 5 cells (20 blocks)
MODE = 9           # majority filter: smallest patch ~36 blocks
SUBS = 4           # WorldCover sub-samples per cell side
FIELD_CELL = 16    # old-field succession patches (~64 blocks)
GAP_CELL = 60      # windthrow gap spacing (~240 blocks)
ALPINE_M = 1700.0  # real metres above which open land is alpine meadow
WC_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{}_Map.tif"
WC_PX = 4500       # overview read per 3x3 degree tile (~67 m)

SUB = ["floodplain_meadow", "wet_meadow_fen", "mossy_ravine", "shaded_conifer_slope", "dry_grassland_slope",
       "warm_oak_scrub_slope", "ridge_heath", "old_field_meadow", "hawthorn_scrub", "young_birch_wood",
       "rough_pasture", "old_growth", "secondary_forest", "windthrow_clearing", "rubble_scrubland", "alpine_meadow",
       "bare"]
S = {s: i for i, s in enumerate(SUB)}
KEEP = None   # mapping value meaning: keep the formation biome

# Formation biomes by group. A biome in no group (oceans, beaches, swamp, peaks not listed) is never changed.
GROUPS = {
    "broadleaf": ["minecraft:forest", "minecraft:birch_forest", "minecraft:flower_forest", "minecraft:dark_forest",
                  "minecraft:old_growth_birch_forest", "minecraft:plains", "minecraft:meadow", "minecraft:cherry_grove",
                  "terralith:sakura_valley", "terralith:sakura_grove", "terralith:blooming_plateau", "terralith:blooming_valley"],
    "conifer": ["terralith:forested_highlands", "minecraft:windswept_forest", "minecraft:grove", "minecraft:old_growth_spruce_taiga",
                "minecraft:old_growth_pine_taiga", "minecraft:taiga", "terralith:alpine_grove", "terralith:temperate_highlands",
                "terralith:highlands", "terralith:birch_taiga"],
    "mountain": ["terralith:rocky_mountains", "terralith:granite_cliffs", "minecraft:stony_peaks", "minecraft:windswept_hills",
                 "terralith:haze_mountain", "minecraft:snowy_slopes"],
    "dry": ["terralith:rocky_shrubland", "terralith:shrubland", "terralith:hot_shrubland", "terralith:lavender_forest",
            "terralith:lavender_valley"],
}
# class -> biome per group; missing class = keep the formation biome
MAP = {
    "broadleaf": {"floodplain_meadow": "terralith:lush_valley", "wet_meadow_fen": "minecraft:swamp", "mossy_ravine": "minecraft:dark_forest",
                  "shaded_conifer_slope": "minecraft:taiga", "dry_grassland_slope": "terralith:valley_clearing",
                  "warm_oak_scrub_slope": "terralith:shrubland", "ridge_heath": "terralith:highlands", "old_field_meadow": "minecraft:plains",
                  "hawthorn_scrub": "terralith:brushland", "young_birch_wood": "minecraft:birch_forest", "rough_pasture": "minecraft:meadow",
                  "secondary_forest": "minecraft:forest", "windthrow_clearing": "terralith:valley_clearing",
                  "rubble_scrubland": "terralith:shrubland", "alpine_meadow": "minecraft:meadow"},
    "conifer": {"floodplain_meadow": "terralith:lush_valley", "wet_meadow_fen": "minecraft:swamp",
                "mossy_ravine": "minecraft:old_growth_spruce_taiga", "shaded_conifer_slope": "minecraft:old_growth_spruce_taiga",
                "dry_grassland_slope": "terralith:alpine_highlands", "ridge_heath": "terralith:alpine_highlands",
                "old_field_meadow": "minecraft:meadow", "hawthorn_scrub": "terralith:highlands", "young_birch_wood": "terralith:birch_taiga",
                "rough_pasture": "terralith:alpine_highlands", "windthrow_clearing": "terralith:valley_clearing",
                "rubble_scrubland": "terralith:highlands", "alpine_meadow": "minecraft:meadow"},
    "mountain": {"alpine_meadow": "minecraft:meadow", "rough_pasture": "terralith:alpine_highlands", "old_field_meadow": "minecraft:meadow",
                 "ridge_heath": "terralith:alpine_highlands"},
    "dry": {"floodplain_meadow": "terralith:lush_valley", "old_field_meadow": "minecraft:plains", "hawthorn_scrub": "terralith:brushland",
            "rough_pasture": "terralith:valley_clearing", "dry_grassland_slope": "terralith:valley_clearing",
            "young_birch_wood": "terralith:shrubland", "rubble_scrubland": "terralith:shrubland", "alpine_meadow": "minecraft:meadow"},
}


def hash01(i, j, salt):
    with np.errstate(over="ignore"): return _hash01(np.asarray(i, np.int64), np.asarray(j, np.int64), salt)


def _hash01(i, j, salt):
    h = (i * 73856093) ^ (np.asarray(j, np.int64) * 19349663) ^ salt
    h = (h ^ (h >> 13)) * 1274126177 & 0x7FFFFFFF
    return (h % 100000) / 100000.0


def voronoi(I, J, cell, salt):
    """Jittered-grid Voronoi on world cell indices: hash value per cell, stable across bakes and regions."""
    ci, cj = I // cell, J // cell; best = np.full(I.shape, 1e18); val = np.zeros(I.shape)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            a, b = ci + di, cj + dj
            sy = (a + hash01(a, b, salt)) * cell; sx = (b + hash01(a, b, salt + 1)) * cell
            d = (I - sy) ** 2 + (J - sx) ** 2; m = d < best
            best = np.where(m, d, best); val = np.where(m, hash01(a, b, salt + 2), val)
    return val


def gaps(I, J, cell, salt):
    """Round disturbance gaps, radius 2-6 cells, at 60% of jittered grid points."""
    out = np.zeros(I.shape, bool); ci, cj = I // cell, J // cell
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            a, b = ci + di, cj + dj
            sy = (a + hash01(a, b, salt)) * cell; sx = (b + hash01(a, b, salt + 1)) * cell
            r = 2 + 4 * hash01(a, b, salt + 3)
            out |= (hash01(a, b, salt + 2) < 0.6) & ((I - sy) ** 2 + (J - sx) ** 2 < r * r)
    return out


def mode_filter(a, size, classes):
    best = np.full(a.shape, -1.0, np.float32); out = a.copy()
    for c in classes:
        f = ndi.uniform_filter((a == c).astype(np.float32), size); m = f > best; best = np.where(m, f, best); out = np.where(m, c, out)
    return out


def worldcover(lon, lat, cache):
    """Class per point (ESA WorldCover codes; 0 = no data)."""
    import rasterio
    from rasterio.enums import Resampling
    out = np.zeros(lon.shape, np.uint8)
    for la in range(int(math.floor(lat.min() / 3) * 3), int(math.ceil(lat.max() / 3) * 3), 3):
        for lo in range(int(math.floor(lon.min() / 3) * 3), int(math.ceil(lon.max() / 3) * 3), 3):
            name = f"{'N' if la >= 0 else 'S'}{abs(la):02d}{'E' if lo >= 0 else 'W'}{abs(lo):03d}"; p = os.path.join(cache, f"wc_{name}.npy")
            if not os.path.exists(p):
                try:
                    with rasterio.open(WC_URL.format(name)) as src: a = src.read(1, out_shape=(WC_PX, WC_PX), resampling=Resampling.mode)
                except rasterio.errors.RasterioIOError as e:     # all-sea tiles do not exist; anything else is an error
                    if "404" not in str(e) and "does not exist" not in str(e) and "No such file" not in str(e): raise
                    print("worldcover", name, "missing (sea)"); a = np.zeros((1, 1), np.uint8)
                np.save(p, a)
            a = np.load(p); m = (lat >= la) & (lat < la + 3) & (lon >= lo) & (lon < lo + 3)
            if a.shape[0] == 1 or not m.any(): continue
            n = a.shape[0]; r = np.clip(((la + 3 - lat[m]) / 3 * n).astype(int), 0, n - 1); c = np.clip(((lon[m] - lo) / 3 * n).astype(int), 0, n - 1)
            out[m] = a[r, c]
    return out


def classify(zr, wc_frac, I, J, cell_m):
    """Sub-biome class per cell from real-metre terrain and land-use fractions (rules of sb1, first match wins)."""
    tree, crop, grass, built, wet, water, bare = (wc_frac[k] for k in ("tree", "crop", "grass", "built", "wet", "water", "bare"))
    zs = ndi.gaussian_filter(zr, 0.75)
    gy, gx = np.gradient(zs, cell_m); slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    north = np.where(slope < 3, 0, gy / np.maximum(np.hypot(gx, gy), 1e-6))   # row 0 is north: downhill to north = rising southwards
    tpi_s = zs - ndi.uniform_filter(zs, 5); tpi_l = zs - ndi.uniform_filter(zs, 21)
    import fastscapelib as fs
    H, W = zr.shape
    grid = fs.RasterGrid([H, W], [cell_m] * 2, fs.NodeStatus.FIXED_VALUE)
    fg = fs.FlowGraph(grid, [fs.SingleFlowRouter(), fs.MSTSinkResolver()]); fg.update_routes(zs.astype(np.float64))
    A = (fg.accumulate(np.ones((H, W))) / 1e6).astype(np.float32)
    field_v = voronoi(I, J, FIELD_CELL, 11); gap = gaps(I, J, GAP_CELL, 23)
    d_forest = ndi.distance_transform_edt(tree < 0.5) * 4                      # blocks
    d_built = ndi.distance_transform_edt(built < 0.3) * cell_m / 1000           # km real
    forest, cropland = tree >= 0.5, crop >= 0.4
    rules = [
        ("bare",                 (bare >= 0.5) | (water >= 0.5)),
        ("alpine_meadow",        (zr > ALPINE_M) & (slope < 25) & ~forest),
        ("floodplain_meadow",    (A > 3000) & (slope < 2) & (tpi_l < 0) & ~forest),
        ("wet_meadow_fen",       (wet >= 0.3) | ((tpi_s < -6) & (slope < 2) & (A < 25) & ~forest)),
        ("mossy_ravine",         (slope > 18) & (tpi_s < -12)),
        ("rubble_scrubland",     built >= 0.5),
        ("shaded_conifer_slope", (slope > 10) & (north > 0.5)),
        ("dry_grassland_slope",  (slope > 10) & (north < -0.5) & ~forest),
        ("warm_oak_scrub_slope", (slope > 10) & (north < -0.5)),
        ("ridge_heath",          (tpi_l > 35) & (slope < 12) & (~forest | (field_v < 0.3))),
        ("windthrow_clearing",   forest & gap),
        ("old_growth",           forest & (d_built > 6)),
        ("secondary_forest",     forest),
        ("young_birch_wood",     cropland & (field_v < np.clip(0.6 - d_forest / 400, 0.15, 0.6))),
        ("hawthorn_scrub",       cropland & (field_v < 0.75)),
        ("old_field_meadow",     cropland),
        ("rough_pasture",        np.ones(zr.shape, bool)),
    ]
    L3 = np.full(zr.shape, 255, np.uint8)
    for name, m in rules: L3[(L3 == 255) & m] = S[name]
    return mode_filter(L3, MODE, range(len(SUB)))


def read_level(adir, lv, T):
    i0, j0, i1, j1 = lv["cells"]; H, W = j1 - j0, i1 - i0
    y = np.full((H, W), np.nan, np.float32); b = np.full((H, W), 255, np.uint8); rel = np.zeros((H, W), np.uint8); n = T * T
    for tz in range(j0 // T, j1 // T):
        for tx in range(i0 // T, i1 // T):
            raw = gzip.open(os.path.join(adir, lv["dir"], f"{tx}_{tz}.bin.gz")).read()
            sl = (slice(tz * T - j0, (tz + 1) * T - j0), slice(tx * T - i0, (tx + 1) * T - i0))
            h = np.frombuffer(raw[8:8 + 2 * n], "<i2").reshape(T, T)
            y[sl] = np.where(h == -32768, np.nan, h / 8.0); rel[sl] = np.frombuffer(raw[8 + 2 * n:8 + 3 * n], "u1").reshape(T, T)
            b[sl] = np.frombuffer(raw[8 + 3 * n:8 + 4 * n], "u1").reshape(T, T)
    return y, rel, b


def write_biomes(adir, lv, T, b):
    i0, j0, i1, j1 = lv["cells"]; n = T * T
    for tz in range(j0 // T, j1 // T):
        for tx in range(i0 // T, i1 // T):
            p = os.path.join(adir, lv["dir"], f"{tx}_{tz}.bin.gz"); raw = bytearray(gzip.open(p).read())
            raw[8 + 3 * n:8 + 4 * n] = b[tz * T - j0:(tz + 1) * T - j0, tx * T - i0:(tx + 1) * T - i0].tobytes()
            with gzip.open(p + ".part", "wb", compresslevel=6) as f: f.write(bytes(raw))
            os.replace(p + ".part", p)


def walk(F, n=400, length=500):
    """Median run (blocks) between biome changes along straight walks, ignoring runs under 2 cells."""
    H, W = F.shape; runs = []
    for k in range(n):
        h = hash01(k, 7, 99); ang = h * math.pi; r0 = int(length / 2 + hash01(k, 8, 99) * (H - length)); c0 = int(length / 2 + hash01(k, 9, 99) * (W - length))
        t = np.arange(-length // 2, length // 2); s = F[np.clip((r0 + t * math.sin(ang)).astype(int), 0, H - 1), np.clip((c0 + t * math.cos(ang)).astype(int), 0, W - 1)]
        seg = np.split(s, np.flatnonzero(np.diff(s) != 0) + 1); keep = [x for x in seg if len(x) >= 2]; merged = []
        for x in keep:
            if merged and merged[-1][0] == x[0]: merged[-1] = np.concatenate([merged[-1], x])
            else: merged.append(x)
        runs += [len(x) * 4 for x in merged[1:-1]]
    return float(np.median(runs)) if runs else float(length * 4)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("atlas"); ap.add_argument("tiles"); ap.add_argument("wc_cache")
    ap.add_argument("--version", default="slice-5"); ap.add_argument("--render")
    a = ap.parse_args(); os.makedirs(a.wc_cache, exist_ok=True); t0 = time.time()
    mpath = os.path.join(a.atlas, "atlas.json"); m = json.load(open(mpath)); T = m["tile_size"]; pal = m["biome_palette"]
    if "subbiomes" in m: sys.exit("atlas already has sub-biomes; rebake L1 first")
    lv = next(l for l in m["levels"] if l["cell"] == 4); i0, j0, i1, j1 = lv["cells"]
    y, rel, b0 = read_level(a.atlas, lv, T); H, W = b0.shape
    J, I = np.mgrid[j0:j1, i0:i1]                     # J = z index (rows), I = x index
    lon, lat, _ = ee_inv(((I + 0.5) * 4 * MPB).astype(np.float64), (-(J + 0.5) * 4 * MPB).astype(np.float64))
    zr = terrarium(lon, lat, 10, a.tiles) - SEA_RISE
    # land-use fractions from SUBS x SUBS points per cell
    acc = {k: np.zeros((H, W), np.float32) for k in ("tree", "crop", "grass", "built", "wet", "water", "bare", "shrub")}
    codes = {"tree": (10,), "shrub": (20,), "grass": (30,), "crop": (40,), "built": (50,), "bare": (60, 70), "water": (80,), "wet": (90, 95)}
    for sa in range(SUBS):
        for sb in range(SUBS):
            lo2, la2, _ = ee_inv(((I + (sa + 0.5) / SUBS) * 4 * MPB).astype(np.float64), (-(J + (sb + 0.5) / SUBS) * 4 * MPB).astype(np.float64))
            wc = worldcover(lo2, la2, a.wc_cache)
            for k, cs in codes.items(): acc[k] += np.isin(wc, cs)
    frac = {k: v / SUBS ** 2 for k, v in acc.items()}
    if sum(float(v.mean()) for v in frac.values()) < 0.5: sys.exit("WorldCover covers under half the cells: check the download (CURL_CA_BUNDLE)")
    for k in ("tree", "crop", "grass", "built", "wet"): frac[k] = ndi.uniform_filter(frac[k], LEG)
    print(f"inputs {time.time() - t0:.0f} s; worldcover shares", {k: round(float(v.mean()), 3) for k, v in frac.items()}, flush=True)
    L3 = classify(zr.astype(np.float32), frac, I, J, 4 * MPB)
    # class x group -> biome
    pix = {k: n for n, k in enumerate(pal)}
    def pid(k):
        if k not in pix: pix[k] = len(pal); pal.append(k)
        return pix[k]
    group = np.full(len(pal), -1, np.int16); gnames = list(GROUPS)
    for g, ids in GROUPS.items():
        for k in ids:
            if k in pix: group[pix[k]] = gnames.index(g)
    lut = np.full((len(gnames), len(SUB)), -1, np.int32)
    for gi, g in enumerate(gnames):
        for c, k in MAP[g].items(): lut[gi, S[c]] = pid(k)
    b = b0.copy(); gcell = np.where(b0 == 255, -1, group[np.minimum(b0, len(group) - 1)])
    ok = (gcell >= 0) & (L3 != 255); new = np.full(b.shape, -1, np.int32)
    new[ok] = lut[gcell[ok], L3[ok]]; ch = new >= 0
    b[ch] = new[ch].astype(np.uint8)
    assert len(pal) < 255, "palette over 254 entries"
    inner = (slice(64, H - 64), slice(64, W - 64))     # outside the L0 feather band
    land = (b0 != 255) & (group[np.minimum(b0, len(group) - 1)] >= 0)
    st = {"changed_pct_of_grouped_land": round(100 * float(ch[land].mean()), 1),
          "median_run_blocks_before": walk(b0[inner]), "median_run_blocks_after": walk(b[inner]),
          "class_pct": {s: round(100 * float((L3[land] == i).mean()), 1) for i, s in enumerate(SUB)}}
    print(json.dumps(st, indent=1), flush=True)
    write_biomes(a.atlas, lv, T, b)
    m["biome_palette"] = pal; m["atlas_version"] = a.version
    m["subbiomes"] = {"level": lv["name"], "classes": SUB, "sources": "ESA WorldCover 2021 v200 (CC BY 4.0); Terrarium z10", **{k: st[k] for k in ("median_run_blocks_before", "median_run_blocks_after")}}
    json.dump(m, open(mpath + ".part", "w"), indent=1); os.replace(mpath + ".part", mpath)
    print(f"done {time.time() - t0:.0f} s, palette {len(pal)}")
    if a.render: render(a.render, b0, b, pal, y)


def render(path, b0, b, pal, y):
    from PIL import Image
    from matplotlib.colors import LightSource, hsv_to_rgb
    def colour(k):
        h = (hash01(sum(map(ord, k)), len(k), 5)); return hsv_to_rgb([h, 0.55, 0.85])
    P = np.array([colour(k) for k in pal] + [(0, 0, 0)] * (256 - len(pal)), np.float32)
    for k, c in {"minecraft:ocean": (0.2, 0.35, 0.7), "minecraft:deep_ocean": (0.12, 0.25, 0.6), "minecraft:forest": (0.2, 0.5, 0.2),
                 "minecraft:plains": (0.8, 0.85, 0.45), "minecraft:meadow": (0.6, 0.85, 0.5), "minecraft:swamp": (0.35, 0.45, 0.3),
                 "minecraft:birch_forest": (0.5, 0.75, 0.4), "minecraft:dark_forest": (0.1, 0.3, 0.12)}.items():
        if k in pal: P[pal.index(k)] = c
    hs = LightSource(315, 40).hillshade(np.nan_to_num(y, nan=0.0), vert_exag=1, dx=4, dy=4)
    ims = [np.clip(P[x] * (0.55 + 0.6 * hs)[..., None], 0, 1) for x in (b0, b)]
    img = np.concatenate([ims[0], np.ones((ims[0].shape[0], 8, 3)), ims[1]], axis=1)
    Image.fromarray((img * 255).astype(np.uint8)).save(path, optimize=True)


if __name__ == "__main__":
    main()
