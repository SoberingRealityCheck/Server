"""Region layer for the atlas: which ecoregion unit (variants/regions.py) each 32-block cell is in.

Writes regions.bin.gz ("EREG", u16 2, u16 cell, i32 i0, i32 j0, i32 w, i32 h, u16[w*h] little-endian) and adds
"regions" to atlas.json. Unit 0 = none (sea), unit n = names[n-1]. Covers the whole globe.
Borders are domain-warped so they do not follow the ecoregion polygons' straight segments. Land in the atlas
that the polygons miss (the atlas coast is not the polygons' coast) takes the nearest ecoregion; so does
Rock and Ice (ECO_ID 0) within ROCK_REACH cells, beyond which it is its own unit.

Also writes, for the variant generator:
  variants/data/ecoregions.json   ECO_ID -> name, WWF biome, realm
  variants/data/unit_biomes.json  unit -> {atlas L0 biome: cells}

Usage: python3 bake_regions.py ATLAS_DIR ECOREGIONS_SHP VARIANTS_DIR
(Ecoregions2017.shp from https://storage.googleapis.com/teow2016/Ecoregions2017.zip, CC BY 4.0, RESOLVE.)
"""
import gzip, json, math, os, struct, sys, time
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake_atlas import ee_inv, value_noise, MPB, BOUNDS, LEVELS, P

CELL = LEVELS[0]["cell"]   # blocks (profile): same as L0
RES = 0.02         # degrees, polygon raster
WARP_DEG = 0.12    # degrees: border warp amplitude
WARP_WAVE_M = 40000.0
ROCK_REACH = 40    # cells
SHORE_CELLS = 24   # cells: units reach this far over the sea, so flat coasts the bake flooded but the game keeps dry have a region
BAND = 256         # rows per projection band


def load_l0(adir, i0, j0, w, h):
    """Global L0 biome palette index on the region grid (255 = no data)."""
    m = json.load(open(os.path.join(adir, "atlas.json"))); T = m["tile_size"]; n = T * T
    lv = next(l for l in m["levels"] if l["name"] == "L0"); out = np.full((h, w), 255, np.uint8)
    for f in os.listdir(os.path.join(adir, lv["dir"])):
        tx, tz = map(int, f.split(".")[0].split("_")); raw = gzip.open(os.path.join(adir, lv["dir"], f)).read()
        b = np.frombuffer(raw[8 + 3 * n:8 + 4 * n], "u1").reshape(T, T)
        a0, c0 = tz * T - j0, tx * T - i0
        ra, rb = max(a0, 0), min(a0 + T, h); ca, cb = max(c0, 0), min(c0 + T, w)
        if ra < rb and ca < cb: out[ra:rb, ca:cb] = b[ra - a0:rb - a0, ca - c0:cb - c0]
    return out, m["biome_palette"]


def detail_pairs(adir, units, i0, j0):
    """(unit, biome) -> area in 32-block cells, over the detail levels' tiles."""
    m = json.load(open(os.path.join(adir, "atlas.json"))); T = m["tile_size"]; n = T * T; acc = {}
    for lv in m["levels"]:
        if lv["name"] == "L0": continue
        k = CELL // lv["cell"]; h, w = units.shape
        for f in os.listdir(os.path.join(adir, lv["dir"])):
            tx, tz = map(int, f.split(".")[0].split("_")); raw = gzip.open(os.path.join(adir, lv["dir"], f)).read()
            b = np.frombuffer(raw[8 + 3 * n:8 + 4 * n], "u1").reshape(T, T)
            J, I = np.mgrid[tz * T:(tz + 1) * T, tx * T:(tx + 1) * T]
            r = np.floor_divide(J, k) - j0; c = np.floor_divide(I, k) - i0
            ok = (r >= 0) & (r < h) & (c >= 0) & (c < w)
            u = np.zeros(b.shape, np.int64); u[ok] = units[r[ok], c[ok]]; sel = (u > 0) & (b != 255)
            vals, cnt = np.unique(u[sel] * 256 + b[sel], return_counts=True)
            for v, ct in zip(vals, cnt):
                key = divmod(int(v), 256); acc[key] = acc.get(key, 0.0) + ct / (k * k)
    return acc


def main():
    adir, shp, vdir = sys.argv[1:4]; t0 = time.time()
    sys.path.insert(0, vdir); import regions as R
    splits = R.split_groups()
    import shapefile
    from rasterio import features, transform
    sf = shapefile.Reader(shp, encoding="latin-1"); shapes = []; meta = {}
    for sr in sf.iterShapeRecords():
        r = sr.record; eid = int(r["ECO_ID"])
        if eid < 0: continue
        shapes.append((sr.shape.__geo_interface__, eid))
        meta[eid] = {"name": r["ECO_NAME"], "biome_num": int(r["BIOME_NUM"]), "biome": r["BIOME_NAME"], "realm": r["REALM"]}
    W, H = int(360 / RES), int(180 / RES)
    eco = features.rasterize(shapes, out_shape=(H, W), transform=transform.from_origin(-180, 90, RES, RES), fill=-1, dtype="int16")
    print(f"raster {W}x{H}, {len(shapes)} polygons, {time.time() - t0:.0f} s", flush=True)
    i0, i1 = int(math.floor(BOUNDS["xmin"] / CELL)), int(math.ceil(BOUNDS["xmax"] / CELL))
    j0, j1 = int(math.floor(BOUNDS["zmin"] / CELL)), int(math.ceil(BOUNDS["zmax"] / CELL))
    w, h = i1 - i0, j1 - j0
    e = np.full((h, w), -1, np.int16); lonw = np.zeros((h, w), np.float32)
    for a in range(0, h, BAND):
        J, I = np.mgrid[j0 + a:j0 + min(a + BAND, h), i0:i1]
        xm = (I + 0.5) * CELL * MPB; ym = -(J + 0.5) * CELL * MPB
        lon, lat, ok = ee_inv(xm.astype(np.float64), ym.astype(np.float64))
        wl = WARP_DEG * (value_noise(xm, ym, WARP_WAVE_M, 71) + 0.5 * value_noise(xm, ym, WARP_WAVE_M / 3, 72) - 0.75)
        wo = WARP_DEG * (value_noise(xm, ym, WARP_WAVE_M, 73) + 0.5 * value_noise(xm, ym, WARP_WAVE_M / 3, 74) - 0.75) / np.maximum(np.cos(np.radians(lat)), 0.2)
        lw = (lon + wo + 180) % 360 - 180; aw = np.clip(lat + wl, -89.999, 89.999)
        r = np.clip(((90 - aw) / RES).astype(int), 0, H - 1); c = np.clip(((lw + 180) / RES).astype(int), 0, W - 1)
        e[a:a + J.shape[0]] = np.where(ok, eco[r, c], -1); lonw[a:a + J.shape[0]] = lw
    del eco
    print(f"grid {w}x{h}, {time.time() - t0:.0f} s", flush=True)
    l0, pal = load_l0(adir, i0, j0, w, h)
    ocean = np.array([("ocean" in p) for p in pal] + [True] * (256 - len(pal)))
    land = ~ocean[l0]
    known = e > 0
    dist, idx = ndi.distance_transform_edt(~known, return_indices=True)
    near = e[tuple(idx)]; del idx
    e = np.where((e == 0) & (dist < ROCK_REACH), near, e)
    shore = ~land & (ndi.distance_transform_edt(~land) <= SHORE_CELLS)
    e = np.where((e == -1) & (land | shore), near, e)
    e = np.where(land | shore, e, -1)  # units on atlas land (lakes and rivers included) and the near shore
    del near, dist
    # units
    names = []; out = np.zeros((h, w), np.uint16)
    for eid in sorted(int(v) for v in np.unique(e) if v >= 0):
        m = e == eid
        if eid in splits:
            for g, lo_a, lo_b in splits[eid]:
                names.append(f"eco:{eid}:{g}"); out[m & (lonw >= lo_a) & (lonw < lo_b)] = len(names)
            left = m & (out == 0)
            if left.any(): names.append(f"eco:{eid}"); out[left] = len(names)
        else:
            names.append(f"eco:{eid}"); out[m] = len(names)
    if len(names) > 65535: raise SystemExit("too many units")
    with gzip.open(os.path.join(adir, "regions.bin.gz"), "wb", compresslevel=9) as f:
        f.write(b"EREG" + struct.pack("<HHiiii", 2, CELL, i0, j0, w, h) + out.astype("<u2").tobytes())
    mpath = os.path.join(adir, "atlas.json"); m = json.load(open(mpath))
    m["regions"] = {"file": "regions.bin.gz", "cell": CELL, "names": names,
                    "sources": "RESOLVE Ecoregions 2017 (CC BY 4.0), one unit per ecoregion, splits from variants/regions.py"}
    json.dump(m, open(mpath + ".part", "w"), indent=1); os.replace(mpath + ".part", mpath)
    # generator data
    stats = {}
    flat_u = out.ravel(); flat_b = l0.ravel(); sel = (flat_u > 0) & land.ravel()   # variants come from land cells only
    pair = flat_u[sel].astype(np.int64) * 256 + flat_b[sel]
    vals, cnt = np.unique(pair, return_counts=True)
    for v, c in zip(vals, cnt):
        u, b = divmod(int(v), 256)
        if b < len(pal): stats.setdefault(names[u - 1], {})[pal[b]] = int(c)
    # detail levels (L1, with sub-biomes) carry biomes L0 does not; count them in L0-cell units
    for (u, b), c in detail_pairs(adir, out, i0, j0).items():
        if b < len(pal):
            d = stats.setdefault(names[u - 1], {}); d[pal[b]] = d.get(pal[b], 0) + int(round(c))
    stats = {u: {b: c for b, c in s.items() if "ocean" not in b} for u, s in stats.items()}   # shore cells add no ocean variants
    if P["extent"] != "globe":   # the variant set is defined by the globe; a window must not overwrite it
        print(f"{len(names)} units on {int(sel.sum())} land cells at {CELL} blocks (window: variants/data left as is); {time.time() - t0:.0f} s")
        np.save(os.path.join(adir, "_regions_preview.npy"), out); return
    os.makedirs(os.path.join(vdir, "data"), exist_ok=True)
    with open(os.path.join(vdir, "data", "ecoregions.json"), "w") as f: json.dump({str(k): meta[k] for k in sorted(meta)}, f, indent=0, ensure_ascii=False)
    with open(os.path.join(vdir, "data", "unit_biomes.json"), "w") as f:
        json.dump({u: dict(sorted(s.items(), key=lambda kv: -kv[1])) for u, s in stats.items()}, f, indent=0)
    print(f"{len(names)} units on {int(sel.sum())} land cells at {CELL} blocks; {time.time() - t0:.0f} s")
    np.save(os.path.join(adir, "_regions_preview.npy"), out)


if __name__ == "__main__":
    main()
