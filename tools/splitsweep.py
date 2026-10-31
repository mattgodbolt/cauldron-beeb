#!/usr/bin/env python3
"""Sweep the palette splits' timing (decision 4) across a window and say
where each lands cleanly.

    python3 tools/splitsweep.py FROM TO STEP [--model B-DFS1.2] [--check]

For each SPLIT_SWEEP value it builds build/sweep.ssd with -D SPLIT_SWEEP=n,
shows outdoor scene 8 in the viewer, screenshots it, and counts the
pixels in the panel's rows that show the wrong colour: a split late
leaves the row above's colour at the start of the row below's first
line, one early gives the row above's last line the row below's. The
panel's rows alternate logical 2 between magenta and cyan (row 0 SC0RE
magenta, row 1 the score cyan, row 2 MAGIC magenta, row 3 the magic's
% cyan) over yellow scrolls in logical 1, which turns at row 4. The
title, before it, has splits of its own (decision 13): its screenshot
is counted against tools/mkscreen.py's picture of it, every pixel. With
--check it exits non-zero if any value shows a wrong pixel (make splits).
"""
import argparse
import os
import subprocess
import sys

from PIL import Image

X0, Y0, SCALE = 368, 264, 4         # where jsbeeb's screenshot puts pixel (0, 0)
MAGENTA, CYAN, YELLOW = (255, 0, 255), (0, 255, 255), (255, 255, 0)
# Each panel row's colour of logical 2.
ROW_L2 = [MAGENTA, CYAN, MAGENTA, CYAN]


def wrong(path):
    im = Image.open(path).convert("RGB")
    px = im.load()
    bad = 0
    for row in range(4):
        for line in range(8):
            y = Y0 + SCALE * (row * 8 + line) + 1
            for x in range(256):
                c = px[X0 + SCALE * x + 1, y]
                if c in (MAGENTA, CYAN) and c != ROW_L2[row]:
                    bad += 1
                elif row < 3 and c not in ((0, 0, 0), MAGENTA, CYAN, YELLOW, (0, 255, 0)):
                    bad += 1
    # Row 4's first line is blank in the sky; row 3's last has the scrolls:
    # anything not yellow among their lit pixels is logical 1 changed early.
    y = Y0 + SCALE * 31 + 1
    for x in range(256):
        c = px[X0 + SCALE * x + 1, y]
        if c not in ((0, 0, 0), YELLOW, CYAN):
            bad += 1
    return bad


def title_wrong(path, want):
    """The title's pixels not the colour tools/mkscreen.py made them."""
    px = Image.open(path).convert("RGB").load()
    want = Image.open(want).convert("RGB").resize((256, 192), Image.NEAREST).load()
    return sum(1 for y in range(192) for x in range(256)
               if px[X0 + SCALE * x + 1, Y0 + SCALE * y + 1] != want[x, y])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("start", type=int)
    ap.add_argument("stop", type=int)
    ap.add_argument("step", type=int)
    ap.add_argument("--model", default=os.environ.get("CAULDRON_MODEL", "B-DFS1.2"))
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    baron = next((b for b in ("../baron/build/src/baron",) if os.path.exists(b)), "baron")
    failed = 0
    for n in range(args.start, args.stop + 1, args.step):
        subprocess.run(["tools/asm.sh", "-D", "VIEWER=1", "-D", f"SPLIT_SWEEP={n}", "-o", "build/sweep.ssd", "--title", "SWEEP",
                        "--opt", "3", "--warn", "2", "--symbols", "build/sweep.json", "src/main.6502"],
                       check=True, env={**os.environ, "BARON": baron}, stdout=subprocess.DEVNULL)
        subprocess.run(["node", "tools/play.mjs", "f3,!t,SPACE:tap,@viewer_wait,=view_num:8,@viewer_wait,f3,!s",
                        "build/sweep_", "--disc", "build/sweep.ssd", "--until", "shown", "--model", args.model],
                       check=True, stdout=subprocess.DEVNULL)
        bad = wrong("build/sweep_s.png")
        title = title_wrong("build/sweep_t.png", "build/data/title.png")
        failed += bad > 0 or title > 0
        print(f"SPLIT_SWEEP={n}: {bad} wrong pixels, the title {title}", flush=True)
    return 1 if args.check and failed else 0


if __name__ == "__main__":
    sys.exit(main())
