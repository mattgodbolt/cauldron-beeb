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
from zxpass import scenarios  # noqa: E402

VARS = 41015
IGNORED = {41397}


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
