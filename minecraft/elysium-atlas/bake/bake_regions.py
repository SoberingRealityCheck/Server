"""Region layer for the atlas: which pack region (variants/regions.py) each 32-block cell is in.

Writes regions.bin.gz ("EREG", u16 1, u16 cell, i32 i0, i32 j0, i32 w, i32 h, u8[w*h]) and adds "regions" to
atlas.json. Index 0 = none, n = REGIONS key n-1. Only the bounding box of the listed ecoregions is stored.
Borders are domain-warped so they do not follow the ecoregion polygons' straight segments.

Usage: python3 bake_regions.py ATLAS_DIR ECOREGIONS_SHP REGIONS_PY
(Ecoregions2017.shp from https://storage.googleapis.com/teow2016/Ecoregions2017.zip, CC BY 4.0, RESOLVE.)
"""
import gzip, importlib.util, json, math, os, struct, sys, time
import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake_atlas import ee_fwd, ee_inv, value_noise, MPB

CELL = 32          # blocks
RES = 0.01         # degrees, polygon raster
WARP_DEG = 0.12    # border warp amplitude
WARP_WAVE_M = 40000.0
COAST_FILL = 3     # cells


def main():
    adir, shp, rpy = sys.argv[1:4]; t0 = time.time()
    spec = importlib.util.spec_from_file_location("regions", rpy); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    names = list(mod.REGIONS); eco_to = {}
    for n, (name, r) in enumerate(names_items := list(mod.REGIONS.items()), start=1):
        for e in r["eco"]: eco_to.setdefault(e, []).append((n, r.get("lon", [-180, 180])))
    import shapefile
    from rasterio import features, transform
    sf = shapefile.Reader(shp, encoding="latin-1")
    shapes = []; bbox = [180, 90, -180, -90]
    for sr in sf.iterShapeRecords():
        eid = sr.record["ECO_ID"]
        if eid in eco_to or eid == 0:
            shapes.append((sr.shape.__geo_interface__, eid)); b = sr.shape.bbox
            if eid != 0: bbox = [min(bbox[0], b[0]), min(bbox[1], b[1]), max(bbox[2], b[2]), max(bbox[3], b[3])]
    pad = 1.0; lo0, la0, lo1, la1 = bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad
    W = int(math.ceil((lo1 - lo0) / RES)); H = int(math.ceil((la1 - la0) / RES))
    tf = transform.from_origin(lo0, la1, RES, RES)
    eco = features.rasterize(shapes, out_shape=(H, W), transform=tf, fill=-1, dtype="int32")
    print(f"raster {W}x{H}, {len(shapes)} polygons, {time.time() - t0:.0f} s", flush=True)
    # cells of the region grid covering the box
    xs, zs = [], []
    for lo in np.linspace(lo0, lo1, 60):
        for la in np.linspace(la0, la1, 60):
            x, y = ee_fwd(lo, la); xs.append(x / MPB); zs.append(-y / MPB)
    i0, i1 = int(math.floor(min(xs) / CELL)), int(math.ceil(max(xs) / CELL)); j0, j1 = int(math.floor(min(zs) / CELL)), int(math.ceil(max(zs) / CELL))
    J, I = np.mgrid[j0:j1, i0:i1]
    xm = (I + 0.5) * CELL * MPB; ym = -(J + 0.5) * CELL * MPB
    lon, lat, ok = ee_inv(xm.astype(np.float64), ym.astype(np.float64))
    wl = WARP_DEG * (value_noise(xm, ym, WARP_WAVE_M, 71) + 0.5 * value_noise(xm, ym, WARP_WAVE_M / 3, 72) - 0.75)
    wo = WARP_DEG * (value_noise(xm, ym, WARP_WAVE_M, 73) + 0.5 * value_noise(xm, ym, WARP_WAVE_M / 3, 74) - 0.75) / np.maximum(np.cos(np.radians(lat)), 0.2)
    lw, aw = lon + wo, lat + wl
    r = np.clip(((la1 - aw) / RES).astype(int), 0, H - 1); c = np.clip(((lw - lo0) / RES).astype(int), 0, W - 1)
    inside = ok & (lw >= lo0) & (lw < lo1) & (aw >= la0) & (aw < la1)
    e = np.where(inside, eco[r, c], -1)
    # Rock and Ice (0) takes the nearest listed ecoregion; so does land just off the polygons' coastline
    # (the atlas coast is not the polygons' coast)
    known = e > 0
    dist, idx = ndi.distance_transform_edt(~known, return_indices=True)
    near = e[tuple(idx)]
    e = np.where(((e == 0) & (dist < 40)) | ((e == -1) & (dist <= COAST_FILL)), near, e)
    out = np.zeros(e.shape, np.uint8)
    for eid, targets in eco_to.items():
        m = e == eid
        for n, (a, b) in targets: out[m & (lw >= a) & (lw < b)] = n
    h, w = out.shape
    with gzip.open(os.path.join(adir, "regions.bin.gz"), "wb", compresslevel=9) as f:
        f.write(b"EREG" + struct.pack("<HHiiii", 1, CELL, i0, j0, w, h) + out.tobytes())
    mpath = os.path.join(adir, "atlas.json"); m = json.load(open(mpath))
    m["regions"] = {"file": "regions.bin.gz", "cell": CELL, "names": names,
                    "sources": "RESOLVE Ecoregions 2017 (CC BY 4.0), grouped by variants/regions.py"}
    json.dump(m, open(mpath + ".part", "w"), indent=1); os.replace(mpath + ".part", mpath)
    share = {names[k - 1]: int((out == k).sum()) for k in range(1, len(names) + 1)}
    print(f"regions {w}x{h} cells at {CELL} blocks; cells per region {share}; {time.time() - t0:.0f} s")
    np.save(os.path.join(adir, "_regions_preview.npy"), out)


if __name__ == "__main__":
    main()
