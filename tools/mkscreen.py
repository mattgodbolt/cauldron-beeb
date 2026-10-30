#!/usr/bin/env python3
"""Convert a Spectrum screen (.scr, or 6912 bytes at 16384 of a snapshot)
to MODE 1's bytes in the port's 256 x 192 layout (src/defs.6502).

    python3 tools/mkscreen.py original/Cauldron.scr build/data/title.bin [--png out.png]

It keeps the four Spectrum colours (BRIGHT ignored: the BBC has none) that
cover the most pixels, and draws any other colour as the nearest of those
four by RGB. It also writes <out>_pal.bin, the four BBC physical colours,
which src/main.6502 includes. (A first look at the geometry: the game's
colour scheme is a decision of its own.)
"""
import argparse
import collections
import os

# Spectrum colour (GRB order: 0 black, 1 blue, 2 red, 3 magenta, 4 green,
# 5 cyan, 6 yellow, 7 white) -> BBC physical colour (RGB order: 1 red,
# 2 green, 4 blue).
ZX_TO_BBC = [0, 4, 1, 5, 2, 6, 3, 7]
BBC_RGB = [((c & 1) * 255, (c >> 1 & 1) * 255, (c >> 2 & 1) * 255) for c in range(8)]


def zx_pixels(scr):
    """The 256 x 192 screen as Spectrum colours 0-7, row by row."""
    out = []
    for y in range(192):
        row = ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        line = []
        for cx in range(32):
            attr = scr[6144 + (y // 8) * 32 + cx]
            ink, paper = attr & 7, (attr >> 3) & 7
            b = scr[row + cx]
            line += [ink if b & (0x80 >> bit) else paper for bit in range(8)]
        out.append(line)
    return out


def mode1_bytes(logical):
    """256 x 192 logical colours (0-3) -> 12K of MODE 1 screen memory."""
    mem = bytearray(32 * 24 * 16)
    for y in range(192):
        for x in range(0, 256, 4):
            v = 0
            for p in range(4):
                c = logical[y][x + p]
                v |= ((c >> 1) & 1) << (7 - p) | (c & 1) << (3 - p)
            cell = (y // 8) * 512 + (x // 8) * 16
            mem[cell + (8 if x & 4 else 0) + (y & 7)] = v
    return mem


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scr")
    ap.add_argument("out")
    ap.add_argument("--png")
    args = ap.parse_args()
    scr = open(args.scr, "rb").read()[:6912]
    px = zx_pixels(scr)
    count = collections.Counter(c for line in px for c in line)
    keep = [c for c, _ in count.most_common(4)]
    keep += [c for c in range(8) if c not in keep][:4 - len(keep)]
    keep.sort()

    def nearest(c):
        if c in keep:
            return keep.index(c)
        rgb = BBC_RGB[ZX_TO_BBC[c]]
        return min(range(4), key=lambda i: sum((a - b) ** 2 for a, b in zip(rgb, BBC_RGB[ZX_TO_BBC[keep[i]]])))
    lut = [nearest(c) for c in range(8)]
    logical = [[lut[c] for c in line] for line in px]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    open(args.out, "wb").write(mode1_bytes(logical))
    base, _ = os.path.splitext(args.out)
    open(base + "_pal.bin", "wb").write(bytes(ZX_TO_BBC[c] for c in keep))
    if args.png:
        from PIL import Image
        im = Image.new("RGB", (256, 192))
        im.putdata([BBC_RGB[ZX_TO_BBC[keep[c]]] for line in logical for c in line])
        im.resize((512, 384), Image.NEAREST).save(args.png)


if __name__ == "__main__":
    main()
