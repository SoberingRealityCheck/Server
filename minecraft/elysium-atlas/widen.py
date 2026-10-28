"""Compile-time only: copies of game classes with some nested classes made public, so javac accepts code that uses
them from their own package (src/main/java/net/minecraft/...). At run time the JVM checks class access flags, not
these source-level ones. usage: widen.py GAME_JAR OUT_DIR"""
import struct, sys, zipfile, os

WIDEN = {"net/minecraft/world/level/levelgen/SurfaceRules$Condition", "net/minecraft/world/level/levelgen/SurfaceRules$Context"}
OUTER = "net/minecraft/world/level/levelgen/SurfaceRules"


def patch(b):
    b = bytearray(b); p = 10; n = struct.unpack_from(">H", b, 8)[0]; utf = {}; cls = {}; i = 1
    while i < n:
        t = b[p]
        if t == 1:
            ln = struct.unpack_from(">H", b, p + 1)[0]; utf[i] = b[p + 3:p + 3 + ln].decode("utf-8", "replace"); p += 3 + ln
        elif t == 7: cls[i] = struct.unpack_from(">H", b, p + 1)[0]; p += 3
        elif t in (8, 16, 19, 20): p += 3
        elif t == 15: p += 4
        elif t in (3, 4, 9, 10, 11, 12, 17, 18): p += 5
        elif t in (5, 6): p += 9; i += 1
        else: raise SystemExit(f"constant tag {t}")
        i += 1
    name = lambda ci: utf[cls[ci]]
    acc = p; this = name(struct.unpack_from(">H", b, p + 2)[0])
    if this in WIDEN: struct.pack_into(">H", b, acc, struct.unpack_from(">H", b, acc)[0] | 1)
    p += 6; p += 2 + 2 * struct.unpack_from(">H", b, p)[0]
    for _ in range(2):   # fields, methods
        cnt = struct.unpack_from(">H", b, p)[0]; p += 2
        for _ in range(cnt):
            p += 6; ac = struct.unpack_from(">H", b, p)[0]; p += 2
            for _ in range(ac): p += 6 + struct.unpack_from(">I", b, p + 2)[0]
    ac = struct.unpack_from(">H", b, p)[0]; p += 2
    for _ in range(ac):
        nm = utf[struct.unpack_from(">H", b, p)[0]]; ln = struct.unpack_from(">I", b, p + 2)[0]
        if nm == "InnerClasses":
            q = p + 8
            for _ in range(struct.unpack_from(">H", b, p + 6)[0]):
                if name(struct.unpack_from(">H", b, q)[0]) in WIDEN:
                    f = struct.unpack_from(">H", b, q + 6)[0]; struct.pack_into(">H", b, q + 6, (f & ~0x0006) | 1)
                q += 8
        p += 6 + ln
    return bytes(b)


jar, out = sys.argv[1:]
with zipfile.ZipFile(jar) as z:
    for e in z.namelist():
        if e.startswith(OUTER) and e.endswith(".class"):
            d = os.path.join(out, os.path.dirname(e)); os.makedirs(d, exist_ok=True)
            open(os.path.join(out, e), "wb").write(patch(z.read(e)))
