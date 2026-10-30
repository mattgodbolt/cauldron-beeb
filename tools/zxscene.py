#!/usr/bin/env python3
"""The original's scenes, drawn by its own code headless: the oracle for
the BBC's (tools/drawcmp.py).

    .venv/bin/python tools/zxscene.py [--snap build/cauldron.z80] [--out build/zxscenes]

For each landscape screen k, out_KK.scr: ATTR_P 71 and CLS (as 27022-27032
do), then 55565 (the moon and stars, the panel), then 57228 printing the
screen's 32 columns. For each room r, room_RR.scr: ATTR_P 5 and CLS (as
35546-35571), then 55569 (the panel alone), then 45710 drawing the room
with background 5. Each is the 6912 bytes of the Spectrum's screen.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zx import Spectrum  # noqa: E402
from zxgfx import LAND_ATTR, LAND_MAP, LAND_SCREENS, run_routine  # noqa: E402

ATTR_P, MASK_P, P_FLAG = 23693, 23694, 23697
CLS = 3435
PRINT_OUTDOORS, PRINT_PANEL_ONLY = 55565, 55569
PRINT_LAND, DRAW_ROOM = 57228, 45710


def scene(snap, attr, steps):
    spec = Spectrum(snap)
    m = spec.mem
    m[ATTR_P], m[MASK_P], m[P_FLAG] = attr, 0, 0
    for addr, setup in [(CLS, None)] + steps:
        if setup:
            setup(m)
        assert run_routine(spec, addr), f"{addr} did not return"
    return bytes(m[16384:16384 + 6912])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--out", default="build/zxscenes")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    for k in range(LAND_SCREENS):
        p = LAND_MAP + 32 * k

        def land(m, p=p):
            # 57228 prints under ATTR_P BRIGHT, black paper (zxgfx's check)
            m[ATTR_P], m[MASK_P], m[P_FLAG] = LAND_ATTR | 5, 0, 0
            m[23296], m[23297] = p & 255, p >> 8
        scr = scene(args.snap, 71, [(PRINT_OUTDOORS, None), (PRINT_LAND, land)])
        open(f"{args.out}/out_{k:02d}.scr", "wb").write(scr)
    for r in range(64):
        def room(m, r=r):
            m[23296], m[23297] = r, 5
        scr = scene(args.snap, 5, [(PRINT_PANEL_ONLY, None), (DRAW_ROOM, room)])
        open(f"{args.out}/room_{r:02d}.scr", "wb").write(scr)
    print(f"wrote {LAND_SCREENS} outdoor scenes and 64 rooms to {args.out}")


if __name__ == "__main__":
    main()
