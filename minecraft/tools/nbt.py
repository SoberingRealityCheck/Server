#!/usr/bin/env python3
"""Read-only NBT reader. Just enough to look inside level.dat.

    python3 minecraft/tools/nbt.py path/to/level.dat [key.path ...]

Plain values in, plain values out. A byte that is 0 or 1 comes back as a bool. Compounds become dicts, lists become
lists, arrays become lists of ints. Writes nothing.
"""
import gzip
import struct
import sys

# tag id -> struct format for the fixed-size ones
FIXED = {1: ">b", 2: ">h", 3: ">i", 4: ">q", 5: ">f", 6: ">d"}


def _read(buf, pos, tag):
    if tag == 1:  # byte. 26.x stores boolean gamerules as bytes, so 0/1 -> bool
        v = struct.unpack_from(">b", buf, pos)[0]
        return (bool(v) if v in (0, 1) else v), pos + 1
    if tag in FIXED:
        fmt = FIXED[tag]
        return struct.unpack_from(fmt, buf, pos)[0], pos + struct.calcsize(fmt)
    if tag == 8:  # string
        n = struct.unpack_from(">H", buf, pos)[0]
        return buf[pos + 2 : pos + 2 + n].decode("utf-8", "replace"), pos + 2 + n
    if tag in (7, 11, 12):  # byte / int / long array
        n = struct.unpack_from(">i", buf, pos)[0]
        pos += 4
        size = {7: 1, 11: 4, 12: 8}[tag]
        fmt = {7: "b", 11: "i", 12: "q"}[tag]
        vals = list(struct.unpack_from(f">{n}{fmt}", buf, pos))
        return vals, pos + n * size
    if tag == 9:  # list
        inner, n = struct.unpack_from(">bi", buf, pos)
        pos += 5
        out = []
        for _ in range(n):
            v, pos = _read(buf, pos, inner)
            out.append(v)
        return out, pos
    if tag == 10:  # compound
        out = {}
        while True:
            t = buf[pos]
            pos += 1
            if t == 0:
                return out, pos
            name, pos = _read(buf, pos, 8)
            out[name], pos = _read(buf, pos, t)
    raise ValueError(f"unknown NBT tag {tag} at byte {pos}")


def load(path):
    """level.dat -> nested dict (the unnamed root compound's contents)."""
    buf = gzip.open(path).read()
    assert buf[0] == 10, "not a compound at the root"
    _, pos = _read(buf, 1, 8)  # root name, usually ""
    root, _ = _read(buf, pos, 10)
    return root


def dig(d, dotted):
    for k in dotted.split("."):
        d = d[k]
    return d


if __name__ == "__main__":
    data = load(sys.argv[1])
    if len(sys.argv) == 2:
        data = {k: v for k, v in data.get("Data", data).items() if k != "WorldGenSettings"}
        print(data)
    for key in sys.argv[2:]:
        print(key, "=", dig(data, key))
