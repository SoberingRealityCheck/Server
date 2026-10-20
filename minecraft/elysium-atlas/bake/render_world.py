"""Render generated chunks of a test world: hillshaded surface height coloured by biome, plus height error vs the atlas.

usage: python3 render_world.py WORLD_DIR ATLAS_DIR OUT_PNG
Reads region/*.mca (heightmaps and biomes only).
"""
import gzip, io, json, math, os, struct, sys, zlib, glob, collections
import numpy as np

def nbt(buf):
    f = io.BytesIO(buf)
    def rd(n): return f.read(n)
    def tag(t):
        if t == 1: return struct.unpack(">b", rd(1))[0]
        if t == 2: return struct.unpack(">h", rd(2))[0]
        if t == 3: return struct.unpack(">i", rd(4))[0]
        if t == 4: return struct.unpack(">q", rd(8))[0]
        if t == 5: return struct.unpack(">f", rd(4))[0]
        if t == 6: return struct.unpack(">d", rd(8))[0]
        if t == 7: n = struct.unpack(">i", rd(4))[0]; return rd(n)
        if t == 8: n = struct.unpack(">H", rd(2))[0]; return rd(n).decode("utf-8", "replace")
        if t == 9:
            et = rd(1)[0]; n = struct.unpack(">i", rd(4))[0]; return [tag(et) for _ in range(n)]
        if t == 10:
            d = {}
            while True:
                et = rd(1)[0]
                if et == 0: return d
                k = tag(8); d[k] = tag(et)
        if t == 11: n = struct.unpack(">i", rd(4))[0]; return np.frombuffer(rd(4 * n), ">i4")
        if t == 12: n = struct.unpack(">i", rd(4))[0]; return np.frombuffer(rd(8 * n), ">i8")
        raise ValueError(t)
    t = rd(1)[0]; tag(8); return tag(t)

def unpack(longs, bits, count):
    per = 64 // bits; mask = (1 << bits) - 1; out = np.zeros(count, np.int64)
    u = longs.astype(np.uint64) if longs.dtype != np.uint64 else longs
    for i in range(count):
        out[i] = (int(u[i // per]) >> ((i % per) * bits)) & mask
    return out

def chunks(world):
    for p in glob.glob(os.path.join(world, "region", "*.mca")):
        data = open(p, "rb").read()
        if len(data) < 8192: continue
        for i in range(1024):
            off = struct.unpack(">I", b"\0" + data[i * 4:i * 4 + 3])[0]
            if off == 0: continue
            ln, comp = struct.unpack(">IB", data[off * 4096:off * 4096 + 5])
            raw = data[off * 4096 + 5:off * 4096 + 4 + ln]
            yield nbt(zlib.decompress(raw) if comp == 2 else gzip.decompress(raw) if comp == 1 else raw)

def main():
    world, atlas_dir, out = sys.argv[1:4]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    H = {}; B = {}; minx = minz = 1 << 30; maxx = maxz = -(1 << 30); n = 0
    for c in chunks(world):
        if c.get("Status") not in ("minecraft:full", "full"): continue
        cx, cz, ymin = c["xPos"], c["zPos"], c.get("yPos", -4) * 16
        hm = c["Heightmaps"]
        if "OCEAN_FLOOR" not in hm: continue
        sects = {s["Y"]: s for s in c["sections"]}; height = max(sects) * 16 + 16 - ymin
        bits = max(1, math.ceil(math.log2(height + 1)))
        floor = unpack(hm["OCEAN_FLOOR"], bits, 256).reshape(16, 16) + ymin - 1
        surf = unpack(hm["WORLD_SURFACE"], bits, 256).reshape(16, 16) + ymin - 1
        bio = np.empty((16, 16), object)
        for qz in range(4):
            for qx in range(4):
                y = int(floor[qz * 4, qx * 4]); s = sects.get(y >> 4)
                if s is None or "biomes" not in s: bio[qz*4:qz*4+4, qx*4:qx*4+4] = "?"; continue
                pal = s["biomes"]["palette"]
                if len(pal) == 1: b = pal[0]
                else:
                    bb = max(1, math.ceil(math.log2(len(pal)))); idx = unpack(s["biomes"]["data"], bb, 64)
                    b = pal[idx[((y & 15) >> 2) * 16 + qz * 4 + qx]]
                bio[qz*4:qz*4+4, qx*4:qx*4+4] = b
        H[(cx, cz)] = (floor, surf); B[(cx, cz)] = bio; n += 1
        minx, maxx, minz, maxz = min(minx, cx), max(maxx, cx), min(minz, cz), max(maxz, cz)
    mx = int(np.median([k[0] for k in H])); mz = int(np.median([k[1] for k in H]))
    keep = [k for k in H if abs(k[0] - mx) <= 96 and abs(k[1] - mz) <= 96]   # the probed area, not stray spawn-search chunks
    H = {k: H[k] for k in keep}; B = {k: B[k] for k in keep}; n = len(H)
    minx, maxx = min(k[0] for k in H), max(k[0] for k in H); minz, maxz = min(k[1] for k in H), max(k[1] for k in H)
    print(n, "full chunks", (minx, maxx, minz, maxz))
    W, Hh = (maxx - minx + 1) * 16, (maxz - minz + 1) * 16
    fl = np.full((Hh, W), np.nan); sf = np.full((Hh, W), np.nan); bi = np.full((Hh, W), "", object)
    for (cx, cz), (f, s) in H.items():
        y0, x0 = (cz - minz) * 16, (cx - minx) * 16
        fl[y0:y0+16, x0:x0+16] = f; sf[y0:y0+16, x0:x0+16] = s; bi[y0:y0+16, x0:x0+16] = B[(cx, cz)]
    # atlas comparison, same Catmull-Rom as the mod
    from bake_atlas import cr_sample
    man = json.load(open(os.path.join(atlas_dir, "atlas.json")))
    xs = np.arange(minx * 16, (maxx + 1) * 16) + 0.0; zs = np.arange(minz * 16, (maxz + 1) * 16) + 0.0
    XB, ZB = np.meshgrid(xs, zs)
    lv = man["levels"][1]; c = lv["cell"]; i0, j0, i1, j1 = lv["cells"]
    grid = np.full((j1 - j0, i1 - i0), np.nan)
    for p in glob.glob(os.path.join(atlas_dir, lv["dir"], "*.bin.gz")):
        tx, tz = map(int, os.path.basename(p).split(".")[0].split("_")); raw = gzip.open(p).read(); T = man["tile_size"]
        h = np.frombuffer(raw[8:8 + 2 * T * T], "<i2").reshape(T, T) / 8.0
        a, b = tz * T - j0, tx * T - i0
        if 0 <= a < grid.shape[0] and 0 <= b < grid.shape[1]: grid[a:a + T, b:b + T] = h
    ay = cr_sample(grid, i0, j0, c, XB, ZB)
    d = fl - ay; ok = ~np.isnan(d)
    stats = {"chunks": n, "mean_floor_minus_atlas": float(np.nanmean(d)), "mean_abs": float(np.nanmean(np.abs(d))),
             "p95_abs": float(np.nanpercentile(np.abs(d), 95)), "floor_range": [float(np.nanmin(fl)), float(np.nanmax(fl))],
             "biomes": collections.Counter(bi[ok].ravel().tolist()).most_common(12)}
    print(json.dumps(stats, indent=1))
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    gy, gx = np.gradient(np.nan_to_num(sf, nan=63)); sl = np.arctan(np.hypot(gx, gy)); asp = np.arctan2(-gx, gy)
    hs = np.clip(np.sin(np.radians(45)) * np.cos(sl) + np.cos(np.radians(45)) * np.sin(sl) * np.cos(np.radians(315) - asp), 0, 1)
    names = sorted(set(bi[ok].ravel().tolist())); idx = {k: i for i, k in enumerate(names)}
    bimg = np.vectorize(lambda k: idx.get(k, -1))(bi).astype(float); bimg[~ok] = np.nan
    fig, ax = plt.subplots(1, 3, figsize=(24, 8.5))
    ax[0].imshow(hs, cmap="gray"); ax[0].imshow(np.ma.masked_invalid(sf), cmap="terrain", alpha=0.45, vmin=40, vmax=250)
    water = sf > fl; ax[0].imshow(np.ma.masked_where(~water, water), cmap="Blues", alpha=0.6, vmin=0, vmax=1.2)
    ax[0].set_title("Generated surface (hillshade, water blue)")
    cm = plt.get_cmap("tab20", max(len(names), 2)); im = ax[1].imshow(bimg, cmap=cm, vmin=-0.5, vmax=len(names) - 0.5, interpolation="nearest")
    ax[1].imshow(hs, cmap="gray", alpha=0.35); ax[1].set_title("Biomes at the surface")
    handles = [plt.Rectangle((0, 0), 1, 1, color=cm(i)) for i in range(len(names))]
    ax[1].legend(handles, [k.split(":")[-1] for k in names], loc="lower left", fontsize=7, ncol=2)
    im2 = ax[2].imshow(d, cmap="RdBu_r", vmin=-15, vmax=15); plt.colorbar(im2, ax=ax[2], fraction=0.04)
    ax[2].set_title(f"Terrain floor minus atlas Y (mean |d| {stats['mean_abs']:.1f}, p95 {stats['p95_abs']:.1f} blocks)")
    for a in ax: a.set_xticks([]); a.set_yticks([])
    fig.suptitle(f"Elysium atlas slice: {W} x {Hh} blocks around block ({(minx + maxx) * 8}, {(minz + maxz) * 8})")
    plt.tight_layout(); plt.savefig(out, dpi=80)
    json.dump(stats, open(os.path.splitext(out)[0] + ".json", "w"), indent=1)

if __name__ == "__main__":
    main()
