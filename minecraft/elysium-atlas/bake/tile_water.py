"""Split ATLAS/water.bin.gz (format 2, one file loaded whole) into tiles the mod loads on demand (format 3).

usage: tile_water.py ATLAS_DIR [--keep]

Writes ATLAS/water/index.bin (bucket, lake reach, tile size, the lake table and the list of tiles) and
ATLAS/water/<tx>_<tz>.bin.gz, one per TILE x TILE blocks. A tile holds every river, stream and lake-shore segment
whose reach (the same reach the mod indexes it by) touches the tile, so segments near a tile edge are stored in
both tiles, and the lake-interior buckets inside it. atlas.json "water" then points at the directory. Without
--keep the format 2 file is removed, so a pack ships one copy.
"""
import gzip, json, os, struct, sys
import numpy as np

TILE = 4096                 # blocks per water tile side (64 buckets of 64)
BANK_MIN, CALM_EXTRA = 8, 16   # as in Water.java: a segment's reach is 2 * half width + BANK_MIN + CALM_EXTRA


def read2(path):
    raw = gzip.open(path).read()
    if raw[:4] != b"EWAT": raise SystemExit(f"{path}: not a water file")
    fmt, bucket, reach = struct.unpack_from("<HHi", raw, 4); o = 12
    if fmt != 2: raise SystemExit(f"{path}: format {fmt}, expected 2")
    ns, nr = struct.unpack_from("<ii", raw, o); o += 8
    segs = np.frombuffer(raw, "<f4", ns * 9, o).reshape(ns, 9); o += ns * 36
    (nl,) = struct.unpack_from("<i", raw, o); o += 4
    lakes = np.frombuffer(raw, np.dtype([("level", "<i4"), ("depth", "<f4")]), nl, o); o += nl * 8
    (ne,) = struct.unpack_from("<i", raw, o); o += 4
    edges = np.frombuffer(raw, "<f4", ne * 4, o).reshape(ne, 4); o += ne * 16
    edge_lake = np.frombuffer(raw, "<i4", ne, o); o += ne * 4
    (ni,) = struct.unpack_from("<i", raw, o); o += 4
    interior = np.frombuffer(raw, "<i4", ni * 3, o).reshape(ni, 3)
    return bucket, reach, segs, nr, lakes, edges, edge_lake, interior


def spread(x0, z0, x1, z1, r):
    """(item index, tile x, tile z) for every tile each item's reach box touches."""
    a0 = np.floor((np.minimum(x0, x1) - r) / TILE).astype(np.int64); a1 = np.floor((np.maximum(x0, x1) + r) / TILE).astype(np.int64)
    c0 = np.floor((np.minimum(z0, z1) - r) / TILE).astype(np.int64); c1 = np.floor((np.maximum(z0, z1) + r) / TILE).astype(np.int64)
    nx, nz = a1 - a0 + 1, c1 - c0 + 1; n = nx * nz
    item = np.repeat(np.arange(len(x0)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    return item, a0[item] + k % nx[item], c0[item] + k // nx[item]


def convert(atlas_dir, keep=False):
    src = os.path.join(atlas_dir, "water.bin.gz")
    bucket, reach, segs, nr, lakes, edges, edge_lake, interior = read2(src)
    if TILE % bucket: raise SystemExit("tile size must be a multiple of the bucket")
    r = 2 * np.maximum(segs[:, 6], segs[:, 7]) + BANK_MIN + CALM_EXTRA
    si, sx, sz = spread(segs[:, 0], segs[:, 1], segs[:, 2], segs[:, 3], r)
    ei, ex, ez = spread(edges[:, 0], edges[:, 1], edges[:, 2], edges[:, 3], np.full(len(edges), reach, np.float32))
    per = bucket and TILE // bucket
    ix, iz = np.floor_divide(interior[:, 0], per), np.floor_divide(interior[:, 1], per)

    def groups(item, tx, tz):
        if not len(item): return {}
        key = tx.astype(np.int64) << 32 | (tz.astype(np.int64) & 0xffffffff)
        order = np.lexsort((item, key)); key, item = key[order], item[order]
        cut = np.flatnonzero(np.diff(key)) + 1
        return {(int(k >> 32), int(np.int32(k & 0xffffffff))): v for k, v in zip(key[np.r_[0, cut]], np.split(item, cut))}

    gs, ge, gi = groups(si, sx, sz), groups(ei, ex, ez), groups(np.arange(len(interior)), ix, iz)
    tiles = sorted(set(gs) | set(ge) | set(gi))
    out = os.path.join(atlas_dir, "water"); os.makedirs(out, exist_ok=True)
    for f in os.listdir(out): os.remove(os.path.join(out, f))
    total = 0
    for t in tiles:
        s = gs.get(t, np.zeros(0, np.int64)); s = np.r_[s[s < nr], s[s >= nr]]   # rivers first, then streams
        e = ge.get(t, np.zeros(0, np.int64)); i = gi.get(t, np.zeros(0, np.int64))
        p = os.path.join(out, f"{t[0]}_{t[1]}.bin.gz")
        with gzip.open(p, "wb", compresslevel=6) as f:
            f.write(b"EWTT" + struct.pack("<ii", len(s), int((s < nr).sum())))
            f.write(np.ascontiguousarray(segs[s], "<f4").tobytes())
            f.write(struct.pack("<i", len(e)))
            f.write(np.ascontiguousarray(edges[e], "<f4").tobytes()); f.write(np.ascontiguousarray(edge_lake[e], "<i4").tobytes())
            f.write(struct.pack("<i", len(i))); f.write(np.ascontiguousarray(interior[i], "<i4").tobytes())
        total += os.path.getsize(p)
    with open(os.path.join(out, "index.bin"), "wb") as f:
        f.write(b"EWTI" + struct.pack("<HHii", 3, bucket, reach, TILE))
        f.write(struct.pack("<i", len(lakes))); f.write(lakes.tobytes())
        f.write(struct.pack("<i", len(tiles))); f.write(np.asarray(tiles, "<i4").tobytes())
    m = json.load(open(os.path.join(atlas_dir, "atlas.json")))
    m["water"] = dict(m.get("water", {}), file="water", format=3, tile=TILE)
    json.dump(m, open(os.path.join(atlas_dir, "atlas.json"), "w"), indent=1)
    if not keep: os.remove(src)
    dup = (len(si) + len(ei)) / max(1, len(segs) + len(edges))
    print(f"water: {len(tiles)} tiles of {TILE} blocks, {total / 1e6:.1f} MB, segments stored {dup:.2f}x on average")


if __name__ == "__main__":
    convert(sys.argv[1], "--keep" in sys.argv)
