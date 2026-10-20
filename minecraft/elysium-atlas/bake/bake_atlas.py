"""Bake the runtime atlas read by the elysium_atlas mod.

Output (a folder the server reads from config/elysium_atlas/):
  atlas.json            manifest: projection, scale, sea level, levels, biome palette, spawn
  L0/<tx>_<tz>.bin.gz   global level, 32 blocks per cell (Terrarium z5)
  L1/<tx>_<tz>.bin.gz   detail level, 4 blocks per cell, test region only (Terrarium z10)

Tile = 256 x 256 cells, row-major (z then x), little-endian:
  b"EATL", u16 version, u16 size, i16 height[size*size] (Y * 8), u8 relief[...] (metres / 20), u8 biome[...] (palette index, 255 = none)

World coordinates: block x = Equal Earth x (m) / MPB, block z = -Equal Earth y (m) / MPB. Origin = 11 E, 0 N.
Vertical: split scaling (doc section 10, E5). Broad band (> ~12 km) x8, fine band x1, then metres -> blocks at MPB.

usage: python3 bake_atlas.py OUT_DIR TILE_CACHE [--region lon0 lon1 lat0 lat1] [--no-l0]
"""
import argparse, gzip, json, math, os, struct, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
# Biome inputs (biome_ids_v1.json, biome_v2_global*) live in the project files, not in this repo.
EXP = os.environ.get("ELYSIUM_WORLDGEN_EXPERIMENTS") or os.path.abspath(os.path.join(HERE, "..", "..", "worldgen-experiments"))

# ---- frozen parameters (changing any of these changes terrain everywhere: bump ATLAS_VERSION)
ATLAS_VERSION = "slice-2"
MPB = 150.0                  # metres per block (Medium preset)
LON0 = 11.0; R = 6371008.8   # Equal Earth, metres
SEA_Y = 63                   # Minecraft sea level
SEA_RISE = 12.0              # warm branch, metres (placeholder until the rise is chosen)
E_LOW, E_HIGH, CUT_M = 8.0, 1.0, 12000.0   # band split
OCEAN_DEPTH_BLOCKS = 48.0    # soft cap on ocean depth below sea level
TOP_KNEE, TOP_SPAN = 400.0, 120.0          # soft cap on land height
TILE = 256
LEVELS = [{"name": "L0", "cell": 32, "zoom": 5}, {"name": "L1", "cell": 4, "zoom": 10}]
FEATHER_CELLS = 64           # L1 fades into L0 over this many cells at its edge
BIOME_NOISE_M = 60000.0      # candidate-pick noise wavelength

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796; M3 = math.sqrt(3) / 2
def ee_fwd(lon, lat):
    lam = np.radians((np.asarray(lon) - LON0 + 180) % 360 - 180); th = np.arcsin(M3 * np.sin(np.radians(lat))); t2 = th * th; t6 = t2 ** 3
    x = 2 * math.sqrt(3) * lam * np.cos(th) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    return R * x, R * th * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
def ee_inv(x, y):
    x, y = x / R, y / R; th = y.copy()
    for _ in range(12):
        t2 = th * th; t6 = t2 ** 3
        th -= (th * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1) - y) / (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1)
    t2 = th * th; t6 = t2 ** 3; d = 9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1
    lam = 3 * x * d / (2 * math.sqrt(3) * np.cos(th)); lon = np.degrees(lam)
    return (lon + LON0 + 180) % 360 - 180, np.degrees(np.arcsin(np.clip(np.sin(th) / M3, -1, 1))), np.abs(lon) <= 180
XM = float(ee_fwd(LON0 + 179.999, 0.0)[0]); YM = float(ee_fwd(0.0, 90.0)[1])
BOUNDS = {"xmin": -XM / MPB, "xmax": XM / MPB, "zmin": -YM / MPB, "zmax": YM / MPB}

# ---- Terrarium sampling (bilinear, parallel tile fetch)
def fetch(z, x, y, cache):
    p = os.path.join(cache, f"{z}_{x}_{y}.png")
    if not os.path.exists(p):
        import urllib.request
        u = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
        for i in range(4):
            try:
                data = urllib.request.urlopen(u, timeout=60).read(); open(p + ".part", "wb").write(data); os.replace(p + ".part", p); break
            except Exception as e:
                if i == 3: raise
                time.sleep(2 ** i)
    return p
def load_tile(p):
    a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
def terrarium(lon, lat, z, cache):
    n = 2 ** z; latc = np.clip(lat, -85.05, 85.05)
    fx = (lon + 180) / 360 * n * 256 - 0.5
    fy = (1 - np.log(np.tan(np.radians(latc)) + 1 / np.cos(np.radians(latc))) / math.pi) / 2 * n * 256 - 0.5
    fy = np.clip(fy, 0, n * 256 - 1.001)
    x0 = np.floor(fx).astype(np.int64); y0 = np.floor(fy).astype(np.int64); wx = (fx - x0).astype(np.float32); wy = (fy - y0).astype(np.float32)
    need = set()
    for dx in (0, 1):
        for dy in (0, 1):
            t = np.unique(((((x0 + dx) // 256) % n) * n + (y0 + dy) // 256).ravel()); need.update(t.tolist())
    need = sorted(need)
    with ThreadPoolExecutor(32) as ex:
        paths = dict(zip(need, ex.map(lambda t: fetch(z, t // n, t % n, cache), need)))
    out = np.zeros(lon.shape, np.float32); acc = {}
    def px(xx, yy):
        xx = xx.ravel(); yy = np.clip(yy.ravel(), 0, n * 256 - 1)
        tx = (xx // 256) % n; ty = yy // 256; key = tx * n + ty; v = np.empty(xx.shape, np.float32)
        order = np.argsort(key, kind="stable"); ks, start = np.unique(key[order], return_index=True); end = list(start[1:]) + [key.size]
        for k, s0, e0 in zip(ks.tolist(), start, end):
            idx = order[s0:e0]
            if k not in acc:
                acc[k] = load_tile(paths[k]) if k in paths else np.zeros((256, 256), np.float32)
                if len(acc) > 2048: acc.pop(next(iter(acc)))
            v[idx] = acc[k][yy[idx] % 256, xx[idx] % 256]
        return v.reshape(lon.shape)
    out = (px(x0, y0) * (1 - wx) * (1 - wy) + px(x0 + 1, y0) * wx * (1 - wy) + px(x0, y0 + 1) * (1 - wx) * wy + px(x0 + 1, y0 + 1) * wx * wy)
    return out

# ---- vertical transfer
def to_y(zr, low):
    E = E_LOW * low + E_HIGH * (zr - low)
    land = zr > 0
    yl = SEA_Y + 0.5 + np.maximum(E, 0) / MPB
    yl = np.where(yl > TOP_KNEE, TOP_KNEE + TOP_SPAN * np.tanh((yl - TOP_KNEE) / TOP_SPAN), yl)
    ys = SEA_Y - 0.5 - OCEAN_DEPTH_BLOCKS * np.tanh(np.maximum(-E, 0) / MPB / OCEAN_DEPTH_BLOCKS)
    return np.where(land, yl, ys)

# ---- Catmull-Rom, identical to AtlasLevel.sample() in the mod
def cr_weights(t):
    t2, t3 = t * t, t * t * t
    return [(-t3 + 2 * t2 - t) / 2, (3 * t3 - 5 * t2 + 2) / 2, (-3 * t3 + 4 * t2 + t) / 2, (t3 - t2) / 2]
def cr_sample(grid, i0, j0, cell, xb, zb):
    """grid[z, x] covers cells starting at (i0, j0); xb, zb in blocks."""
    u = xb / cell - 0.5 - i0; v = zb / cell - 0.5 - j0
    iu = np.floor(u).astype(int); iv = np.floor(v).astype(int); wu = cr_weights(u - iu); wv = cr_weights(v - iv)
    out = np.zeros(np.shape(xb), np.float64)
    for a in range(4):
        for b in range(4):
            out += wu[a] * wv[b] * grid[np.clip(iv + b - 1, 0, grid.shape[0] - 1), np.clip(iu + a - 1, 0, grid.shape[1] - 1)]
    return out

# ---- biome assignment
def value_noise(xm, ym, wave, seed):
    gx = xm / wave; gy = ym / wave; ix = np.floor(gx).astype(np.int64); iy = np.floor(gy).astype(np.int64); fx = gx - ix; fy = gy - iy
    def h(a, b):
        k = (a * 73856093) ^ (b * 19349663) ^ seed; k = (k ^ (k >> 13)) * 1274126177; k = k ^ (k >> 16)
        return (k & 0xFFFFFF) / float(0xFFFFFF)
    sx = fx * fx * (3 - 2 * fx); sy = fy * fy * (3 - 2 * fy)
    return (h(ix, iy) * (1 - sx) * (1 - sy) + h(ix + 1, iy) * sx * (1 - sy) + h(ix, iy + 1) * (1 - sx) * sy + h(ix + 1, iy + 1) * sx * sy)

class Biomes:
    def __init__(self):
        m = json.load(open(os.path.join(EXP, "atlas", "biome_ids_v1.json")))
        self.map, self.ovr, self.fb, self.classes = m["map"], m["realm_overrides"], m["fallback"], m["classes"]
        meta = json.load(open(os.path.join(EXP, "globe", "biome_v2_global.json")))
        self.form = [b["id"] for b in meta["biomes"]]; self.realms = meta["realms"]
        d = np.load(os.path.join(EXP, "globe", "biome_v2_global_10m.npz"))
        bio = d["biome"]; idx = ndi.distance_transform_edt(bio == 255, return_distances=False, return_indices=True)
        self.bio = bio[tuple(idx)]; self.realm = d["realm"][tuple(idx)]; self.MI = d["MI"].astype(np.float32)[tuple(idx)]
        self.palette = ["minecraft:warm_ocean", "minecraft:lukewarm_ocean", "minecraft:ocean", "minecraft:cold_ocean", "minecraft:frozen_ocean",
                        "minecraft:deep_lukewarm_ocean", "minecraft:deep_ocean", "minecraft:deep_cold_ocean", "minecraft:deep_frozen_ocean",
                        "minecraft:beach", "minecraft:snowy_beach", "minecraft:stony_shore"]
        self.pix = {k: i for i, k in enumerate(self.palette)}
    def pid(self, k):
        if k not in self.pix: self.pix[k] = len(self.palette); self.palette.append(k)
        return self.pix[k]
    def resolve(self, f, r, c):
        while True:
            o = self.ovr.get(f"{f}|{r}", {})
            if c in o: return o[c]
            if c in self.map[f]: return self.map[f][c]
            c = self.fb[c]
    def assign(self, lon, lat, xm, ym, y, zr, relief, sea, coast_cells):
        H, W = y.shape; out = np.full((H, W), 255, np.uint8)
        # warp the 10' lookup so formation borders do not follow the grid (cells are ~86 x 123 blocks in Europe)
        wl = 0.3 * (value_noise(xm, ym, 14000.0, 11) + 0.5 * value_noise(xm, ym, 5000.0, 13) - 0.75)
        wo = 0.3 * (value_noise(xm, ym, 14000.0, 12) + 0.5 * value_noise(xm, ym, 5000.0, 14) - 0.75) / np.maximum(np.cos(np.radians(lat)), 0.2)
        r10 = np.clip(((90 - lat - wl) / 180 * 1080).astype(int), 0, 1079); c10 = np.clip(((lon + wo + 180) / 360 * 2160).astype(int) % 2160, 0, 2159)
        F = self.bio[r10, c10]; RL = self.realm[r10, c10]; MI = self.MI[r10, c10]
        cls = np.zeros((H, W), np.uint8)
        cls[(relief < 60) & (zr < 150) & (MI >= 1.0)] = 1
        cls[(relief >= 300) | (zr >= 700)] = 2
        cls[(relief >= 1000) | (zr >= 2000)] = 3
        cls[(zr >= 3500) | ((relief >= 1500) & (zr >= 2500))] = 4
        nz = value_noise(xm, ym, BIOME_NOISE_M, 1337)
        land = ~sea
        for fi in np.unique(F[land]):
            for ri in np.unique(RL[land & (F == fi)]):
                for ci in range(5):
                    m = land & (F == fi) & (RL == ri) & (cls == ci)
                    if not m.any(): continue
                    cand = self.resolve(self.form[fi], self.realms[ri], self.classes[ci])
                    cw = np.cumsum([w for _, w in cand]); cw = cw / cw[-1]
                    k = np.searchsorted(cw, nz[m] * 0.99999)
                    out[m] = np.array([self.pid(i) for i, _ in cand], np.uint8)[k]
        # oceans by latitude and depth
        al = np.abs(lat); deep = y < SEA_Y - 20
        oc = np.select([al < 23, al < 35, al < 50, al < 62], [0, 1, 2, 3], 4); dc = np.select([al < 23, al < 35, al < 50, al < 62], [5, 5, 6, 7], 8)
        out[sea] = np.where(deep, dc, oc)[sea]
        # beaches: low land next to sea (detail levels only)
        if coast_cells > 0:
            near = ndi.binary_dilation(sea, iterations=coast_cells) & land & (y < SEA_Y + 3.5)
            cold = np.isin(F, [self.form.index(f) for f in ("ice_sheet", "polar_desert", "arctic_tundra")])
            out[near] = np.where(relief[near] > 300, 11, np.where(cold[near], 10, 9))
        return out

# ---- one level
def bake_level(lv, i0, i1, j0, j1, cache, biomes, l0=None, feather=0):
    c = lv["cell"]; t0 = time.time()
    pad = int(math.ceil(3 * CUT_M / 2 / MPB / c)) + 2           # margin for the low-pass and relief
    I = np.arange(i0 - pad, i1 + pad); J = np.arange(j0 - pad, j1 + pad)
    xb = (I + 0.5) * c; zb = (J + 0.5) * c
    XB, ZB = np.meshgrid(xb, zb); xm = XB * MPB; ym = -ZB * MPB
    lon, lat, ok = ee_inv(xm, ym)
    sub = max(1, int(round(c * MPB / (156543.0 / 2 ** lv["zoom"] * max(math.cos(math.radians(min(abs(float(np.median(lat))), 80))), 0.2)))))
    sub = min(sub, 4)
    if sub > 1:   # area-average sub-samples so a cell is not aliased from one pixel
        acc = np.zeros(XB.shape, np.float64)
        for a in range(sub):
            for b in range(sub):
                lo2, la2, _ = ee_inv(((I[None, :] + (a + 0.5) / sub) * c) * MPB + 0 * ZB, -((J[:, None] + (b + 0.5) / sub) * c) * MPB + 0 * XB)
                acc += terrarium(lo2, la2, lv["zoom"], cache)
        z = (acc / sub / sub).astype(np.float32)
    else:
        z = terrarium(lon, lat, lv["zoom"], cache)
    z = np.where(ok, z, -6000.0).astype(np.float32)
    zr = z - SEA_RISE
    low = ndi.gaussian_filter(zr.astype(np.float64), CUT_M / 2 / MPB / c, mode="nearest")
    y = to_y(zr, low)
    win = max(3, int(round(8000 / MPB / c)) | 1)
    relief = ndi.maximum_filter(zr, win) - ndi.minimum_filter(zr, win)
    sea = zr <= 0
    s = (slice(pad, pad + (j1 - j0)), slice(pad, pad + (i1 - i0)))
    y, zr, relief, sea, lon, lat, xm, ym, XB, ZB = (a[s] for a in (y, zr, relief, sea, lon, lat, xm, ym, XB, ZB))
    if feather and l0 is not None:
        g, gi0, gj0, gc = l0
        y0 = cr_sample(g, gi0, gj0, gc, XB, ZB)
        H, W = y.shape; jj, ii = np.mgrid[0:H, 0:W]
        d = np.minimum(np.minimum(ii, W - 1 - ii), np.minimum(jj, H - 1 - jj)).astype(np.float64)
        w = np.clip(d / feather, 0, 1); w = w * w * (3 - 2 * w)
        y = w * y + (1 - w) * y0
        sea = y < SEA_Y
    b = biomes.assign(lon, lat, xm, ym, y, zr, relief, sea, 2 if c <= 8 else 0)
    print(f"{lv['name']}: {y.shape[1]}x{y.shape[0]} cells, sub {sub}, {time.time() - t0:.0f} s, Y {y.min():.0f}..{y.max():.0f}", flush=True)
    return y, relief, b

def write_tiles(outdir, name, i0, j0, y, relief, b):
    d = os.path.join(outdir, name); os.makedirs(d, exist_ok=True)
    H, W = y.shape; hq = np.clip(np.round(y * 8), -32768, 32767).astype("<i2"); rq = np.clip(relief / 20, 0, 255).astype(np.uint8)
    n = 0
    for tz in range(j0 // TILE, (j0 + H - 1) // TILE + 1):
        for tx in range(i0 // TILE, (i0 + W - 1) // TILE + 1):
            a0, a1 = max(tz * TILE, j0), min((tz + 1) * TILE, j0 + H); b0, b1 = max(tx * TILE, i0), min((tx + 1) * TILE, i0 + W)
            if a0 >= a1 or b0 >= b1: continue
            h = np.full((TILE, TILE), -32768, "<i2"); r = np.zeros((TILE, TILE), np.uint8); bb = np.full((TILE, TILE), 255, np.uint8)
            sl = (slice(a0 - tz * TILE, a1 - tz * TILE), slice(b0 - tx * TILE, b1 - tx * TILE)); src = (slice(a0 - j0, a1 - j0), slice(b0 - i0, b1 - i0))
            h[sl] = hq[src]; r[sl] = rq[src]; bb[sl] = b[src]
            with gzip.open(os.path.join(d, f"{tx}_{tz}.bin.gz"), "wb", compresslevel=6) as f:
                f.write(b"EATL" + struct.pack("<HH", 1, TILE) + h.tobytes() + r.tobytes() + bb.tobytes())
            n += 1
    return n

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("cache")
    ap.add_argument("--region", nargs=4, type=float, default=[4.0, 13.5, 43.5, 48.5], metavar=("LON0", "LON1", "LAT0", "LAT1"))
    ap.add_argument("--spawn", nargs=2, type=float, default=[6.63, 46.53], metavar=("LON", "LAT"))
    ap.add_argument("--no-l0", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); os.makedirs(a.cache, exist_ok=True)
    biomes = Biomes()
    # L0: whole globe, in strips to bound memory
    c0 = LEVELS[0]["cell"]
    gi0 = int(math.floor(BOUNDS["xmin"] / c0)); gi1 = int(math.ceil(BOUNDS["xmax"] / c0)); gj0 = int(math.floor(BOUNDS["zmin"] / c0)); gj1 = int(math.ceil(BOUNDS["zmax"] / c0))
    gi0, gj0 = (gi0 // TILE) * TILE, (gj0 // TILE) * TILE; gi1, gj1 = -(-gi1 // TILE) * TILE, -(-gj1 // TILE) * TILE
    l0_npz = os.path.join(a.out, "_l0_cache.npz")
    if not a.no_l0 or not os.path.exists(l0_npz):
        Y0 = np.zeros((gj1 - gj0, gi1 - gi0), np.float32); n = 0
        for js in range(gj0, gj1, TILE * 2):
            je = min(js + TILE * 2, gj1)
            y, r, b = bake_level(LEVELS[0], gi0, gi1, js, je, a.cache, biomes)
            Y0[js - gj0:je - gj0] = y; n += write_tiles(a.out, "L0", gi0, js, y, r, b)
        np.savez_compressed(l0_npz, Y0=Y0, gi0=gi0, gj0=gj0); print("L0 tiles", n)
    d = np.load(l0_npz); Y0, gi0, gj0 = d["Y0"], int(d["gi0"]), int(d["gj0"])
    # L1: test region box, snapped to tiles
    c1 = LEVELS[1]["cell"]; lo0, lo1, la0, la1 = a.region
    xs, ys_ = [], []
    for lo in np.linspace(lo0, lo1, 40):
        for la in np.linspace(la0, la1, 40):
            x, y = ee_fwd(lo, la); xs.append(x / MPB); ys_.append(-y / MPB)
    i0 = int(math.floor(min(xs) / c1 / TILE)) * TILE; i1 = int(math.ceil(max(xs) / c1 / TILE)) * TILE
    j0 = int(math.floor(min(ys_) / c1 / TILE)) * TILE; j1 = int(math.ceil(max(ys_) / c1 / TILE)) * TILE
    y1, r1, b1 = bake_level(LEVELS[1], i0, i1, j0, j1, a.cache, biomes, l0=(Y0, gi0, gj0, c0), feather=FEATHER_CELLS)
    n1 = write_tiles(a.out, "L1", i0, j0, y1, r1, b1); print("L1 tiles", n1)
    sx, sy = ee_fwd(a.spawn[0], a.spawn[1])
    manifest = {
        "format": 1, "atlas_version": ATLAS_VERSION,
        "projection": {"type": "equal_earth", "lon0": LON0, "radius_m": R},
        "metres_per_block": MPB, "sea_level_y": SEA_Y, "sea_rise_m": SEA_RISE,
        "vertical": {"e_low": E_LOW, "e_high": E_HIGH, "cut_m": CUT_M, "ocean_depth_blocks": OCEAN_DEPTH_BLOCKS, "top_knee": TOP_KNEE, "top_span": TOP_SPAN},
        "bounds_blocks": BOUNDS, "tile_size": TILE,
        "levels": [{"name": "L0", "cell": c0, "dir": "L0"}, {"name": "L1", "cell": c1, "dir": "L1",
                    "cells": [i0, j0, i1, j1], "region_lonlat": a.region}],
        "biome_palette": biomes.palette,
        "spawn": {"x": int(round(sx / MPB)), "z": int(round(-sy / MPB)), "lon": a.spawn[0], "lat": a.spawn[1]},
        "sources": "Terrarium (Mapzen/AWS open data) z5 and z10; biome_v2 formations and biome_ids_v1 mapping",
    }
    json.dump(manifest, open(os.path.join(a.out, "atlas.json"), "w"), indent=1)
    print(json.dumps({k: manifest[k] for k in ("spawn", "levels")}, indent=0), "palette", len(biomes.palette))
    assert len(biomes.palette) < 255

if __name__ == "__main__":
    main()
