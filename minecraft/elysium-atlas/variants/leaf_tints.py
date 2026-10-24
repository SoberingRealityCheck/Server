"""Regional leaf colours for every green leaf, not only the oak family.

Vanilla tints oak, jungle, acacia, dark oak and mangrove leaves from the biome's foliage colour, but gives spruce
and birch fixed colours, and the flora mods' leaves (BOP fir and redwood, Terrestria hemlock, Wilder Wild
baobab, ...) are pre-coloured textures. This makes them all follow the variant's foliage colour while each
species keeps its own character:

  species offset  the species' own colour as a (hue shift, saturation ratio, value ratio) from vanilla's default
                  foliage colour; the mod applies it to the biome's foliage colour (LeafTints.java), so a spruce
                  stays bluer and darker than an oak in every region, and both shift with the region and season
  textures        the mod leaves' textures as greyscale (luminance pattern kept), in the built-in resource pack
                  resourcepacks/regional_leaves, so the tint is not multiplied onto a green texture

Leaves that are not green on purpose (maples, sakura, jacaranda, snowblossom, rainbow eucalyptus, dead and
fantasy leaves) and pale oak, cherry and azalea keep their own colours.

usage: python3 variants/leaf_tints.py CLIENT_JAR BOP_JAR WILDERWILD_JAR TERRESTRIA_JAR
"""
import colorsys, io, json, os, sys, zipfile
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "src", "main", "resources")
PACK = os.path.join(RES, "resourcepacks", "regional_leaves")
FOLIAGE_DEFAULT = 0x48B518
GREY_MEAN = 0.566        # vanilla oak_leaves texture mean, so a retextured leaf is as bright as an oak under the same tint

# vanilla leaves with greyscale textures and fixed tints: species colour = the fixed tint
VANILLA = {"minecraft:spruce_leaves": 0x619961, "minecraft:birch_leaves": 0x80A755, "minecraft:mangrove_leaves": 0x92C033}
# leaves that already follow the foliage colour (vanilla, or tinted by their own mod): listed so a region's palette
# (profile "leaves", leaf_palettes.json) can recolour them; their default offset is none
FOLLOW = ["minecraft:oak_leaves", "minecraft:dark_oak_leaves", "minecraft:acacia_leaves", "minecraft:jungle_leaves",
          "biomesoplenty:pine_leaves"]
# default character for greyscale mod leaves that have no colour of their own to measure (conifers a little bluer
# and darker than broadleaves); a region's palette overrides it
CHARACTER = {"terrestria:hemlock_leaves": (0.04, 0.70, 0.85), "terrestria:redwood_leaves": (0.02, 0.75, 0.85),
             "wilderwild:cypress_leaves": (0.03, 0.75, 0.9), "terrestria:cypress_leaves": (0.04, 0.8, 0.75),
             "biomesoplenty:pine_leaves": (0.03, 0.8, 0.9)}
GREY = 0.15               # mean HSV saturation under which a texture counts as greyscale (tinted by its own mod)
# mod leaves (model parent minecraft:block/leaves, so tint index 0 is already there): pre-coloured textures are
# made greyscale; greyscale ones are kept and only take the regional tint
MOD = ["biomesoplenty:fir_leaves", "biomesoplenty:redwood_leaves", "biomesoplenty:cypress_leaves", "biomesoplenty:palm_leaves",
       "biomesoplenty:willow_leaves", "biomesoplenty:mahogany_leaves",
       "wilderwild:baobab_leaves", "wilderwild:cypress_leaves", "wilderwild:willow_leaves",
       "terrestria:hemlock_leaves", "terrestria:redwood_leaves", "terrestria:cypress_leaves", "terrestria:rubber_leaves",
       "terrestria:jungle_palm_leaves", "terrestria:yucca_palm_leaves"]


def hsv(c): return colorsys.rgb_to_hsv(((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255)


def offset(rgb):
    """(hue shift, saturation ratio, value ratio) of a colour against vanilla's default foliage colour."""
    h, s, v = colorsys.rgb_to_hsv(*rgb); h0, s0, v0 = hsv(FOLIAGE_DEFAULT)
    dh = (h - h0 + 0.5) % 1.0 - 0.5
    return [round(dh, 4), round(s / s0, 4), round(v / v0, 4)]


def main():
    client, *mods = sys.argv[1:]
    zips = [zipfile.ZipFile(client)] + [zipfile.ZipFile(m) for m in mods]
    def read(path):
        for z in zips:
            try: return z.read(path)
            except KeyError: pass
        return None
    table = {}
    for b, c in VANILLA.items():
        table[b] = offset((((c >> 16) & 255) / 255, ((c >> 8) & 255) / 255, (c & 255) / 255))
    for b in FOLLOW: table[b] = list(CHARACTER.get(b, (0.0, 1.0, 1.0)))
    n_grey = 0
    for b in MOD:
        ns, name = b.split(":")
        model = read(f"assets/{ns}/models/block/{name}.json")
        if model is None: print("no model", b); continue
        m = json.loads(model)
        if m.get("parent") not in ("minecraft:block/leaves", "block/leaves"): print("not a plain leaves model, skipped", b); continue
        tex = m["textures"]["all"]; tns, tpath = tex.split(":") if ":" in tex else ("minecraft", tex)
        png = read(f"assets/{tns}/textures/{tpath}.png")
        if png is None: print("no texture", tex); continue
        im = np.asarray(Image.open(io.BytesIO(png)).convert("RGBA")).astype(np.float64) / 255
        a = im[..., 3] > 0.5
        mean = im[..., :3][a].mean(0)
        px = im[..., :3][a]; sat = ((px.max(1) - px.min(1)) / np.maximum(px.max(1), 1e-6)).mean()
        if sat < GREY:            # already a tint target of its own mod: keep the texture, only take our tint
            table[b] = list(CHARACTER.get(b, (0.0, 1.0, 1.0))); n_grey += 1; continue
        lum = im[..., :3] @ np.array([0.299, 0.587, 0.114]); lmean = lum[a].mean()
        # the colour a tint must have to reproduce the original look on a GREY_MEAN texture in a default-foliage biome
        species = np.clip(mean / GREY_MEAN, 0, 1)
        table[b] = offset(tuple(species))
        g = np.clip(lum / lmean * GREY_MEAN, 0, 1)
        out = np.dstack([g, g, g, im[..., 3]])
        dst = os.path.join(PACK, "assets", tns, "textures", f"{tpath}.png"); os.makedirs(os.path.dirname(dst), exist_ok=True)
        Image.fromarray((out * 255).round().astype(np.uint8), "RGBA").save(dst)
        # the item keeps its old look in the inventory: a constant tint of the species colour
        sp = (np.round(species * 255).astype(int)); argb = (0xFF << 24 | sp[0] << 16 | sp[1] << 8 | sp[2]) - (1 << 32)
        item = os.path.join(PACK, "assets", ns, "items", f"{name}.json"); os.makedirs(os.path.dirname(item), exist_ok=True)
        json.dump({"model": {"type": "minecraft:model", "model": f"{ns}:block/{name}", "tints": [{"type": "minecraft:constant", "value": int(argb)}]}},
                  open(item, "w"), indent=1)
        meta = read(f"assets/{tns}/textures/{tpath}.png.mcmeta")
        if meta is not None: open(dst + ".mcmeta", "wb").write(meta)
    os.makedirs(PACK, exist_ok=True)
    json.dump({"pack": {"min_format": [82], "max_format": [32767],
                        "description": "Elysium: regional colours for spruce, birch and the flora mods' green leaves"}},
              open(os.path.join(PACK, "pack.mcmeta"), "w"), indent=1)
    os.makedirs(os.path.join(RES, "elysium_atlas"), exist_ok=True)
    json.dump({"foliage_default": FOLIAGE_DEFAULT, "leaves": table}, open(os.path.join(RES, "elysium_atlas", "leaf_tints.json"), "w"), indent=1)
    print(f"{len(table)} leaf types: {len(VANILLA) + len(FOLLOW)} vanilla or foliage-following, {n_grey} greyscale mod leaves, "
          f"{len(table) - len(VANILLA) - len(FOLLOW) - n_grey} retextured")


if __name__ == "__main__":
    main()
