#!/usr/bin/env python3
"""Compare the original's and the port's variables, pass by pass
(build/passes/<name>.zx.json from tools/zxpass.py, .bbc.json from
tools/beepass.mjs).

    .venv/bin/python tools/passcmp.py [scenario ...]

Reports each scenario's first pass whose variables differ, and which
(by the decompiler's names), and exits non-zero if any do. usr_result
(41397) is left out: it holds the BC a USR routine returned, which no
statement reads and the port doesn't copy.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decompile as D  # noqa: E402
from zxpass import SCREEN_EVERY, scenarios  # noqa: E402

VARS = 41015
IGNORED = {41397}


def screen_diff(scr, bbc):
    """How the BBC's screen (12K, then 768 attributes) differs from the
    Spectrum's (6912 bytes): lit pixels and attributes, or None."""
    lit = 0
    for line in range(192):
        for col in range(32):
            b = scr[((line & 0xC0) << 5) + ((line & 7) << 8) + ((line & 0x38) << 2) + col]
            base = (line >> 3) * 512 + col * 16 + (line & 7)
            l, r = bbc[base], bbc[base + 8]
            got = ((((l >> 4) | l) & 15) << 4) | (((r >> 4) | r) & 15)
            if got != b:
                lit += 1
    attrs = sum(a != b for a, b in zip(scr[6144:], bbc[0x3000:0x3300]))
    if lit or attrs:
        return f"{lit} bytes' lit pixels and {attrs} attributes"
    return None


def name(a):
    return D.var_name(a)


def main():
    want = sys.argv[1:]
    bad = 0
    for sc in scenarios():
        if want and sc not in want:
            continue
        zx = json.load(open(f"build/passes/{sc}.zx.json"))
        bbc = json.load(open(f"build/passes/{sc}.bbc.json"))
        n = min(len(zx), len(bbc))
        first = None
        for i in range(n):
            a, b = bytes.fromhex(zx[i]), bytes.fromhex(bbc[i])
            diffs = []
            for o in range(0, len(a), 2):
                if VARS + o in IGNORED:
                    continue
                va, vb = a[o] | a[o + 1] << 8, b[o] | b[o + 1] << 8
                if va != vb:
                    diffs.append(f"{name(VARS + o)} {va} not {vb}")
            if diffs:
                first = (i, diffs)
                break
        # The screens, every SCREEN_EVERY passes: every pixel lit or not and
        # the attributes, which the port keeps as the original's (decision 5).
        zs = json.load(open(f"build/passes/{sc}.zx.screens.json"))
        bs = json.load(open(f"build/passes/{sc}.bbc.screens.json"))
        for k in range(min(len(zs), len(bs))):
            if first and k * SCREEN_EVERY >= first[0]:
                break
            d = screen_diff(bytes.fromhex(zs[k]), bytes.fromhex(bs[k]))
            if d:
                first = (k * SCREEN_EVERY, [f"the screen: {d}"])
                break
        if first:
            bad += 1
            print(f"{sc}: pass {first[0]} differs: " + "; ".join(first[1][:12]))
        elif len(zx) != len(bbc):
            bad += 1
            print(f"{sc}: the {n} passes the port ran agree; the original ran {len(zx)}")
        else:
            print(f"{sc}: all {n} passes agree")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
