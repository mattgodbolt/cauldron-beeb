#!/usr/bin/env python3
"""Measure the Spectrum original: pacing, where the time goes, what its
drawing routines cost, and the colours on its screens.

    .venv/bin/python tools/zxprobe.py snaps      # build/probe/*.z80, the scenes below
    .venv/bin/python tools/zxprobe.py pace       # frames per main-loop pass
    .venv/bin/python tools/zxprobe.py profile    # share of T-states by routine
    .venv/bin/python tools/zxprobe.py cost       # T-states of single drawing calls
    .venv/bin/python tools/zxprobe.py colours    # attribute and colour counts

The scenes (from build/cauldron.z80, keys CAPS SHIFT to V):

    fly       outdoors, the witch on the ground beside the cottage
    under5    underground, room 4 (door 5's entry room)
    under7    underground, room 14 (door 7's)

To reach the underground without playing there, `snaps` walks the witch
left into the cottage's door test (32569) and, at 32572, when the door
lookup (29908) has returned, names a door and gives its key: (41439)=door,
(41441)=1, and the key flag at 41237+2(door-1).

docs/research/runtime.md and graphics.md quote this tool's output.
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zx import FRAME48, Spectrum, run_script  # noqa: E402

PROBE = "build/probe/"
PASS_MARK = 29505      # the compiled routine that reads the controls (USR 51900), once a pass
NAMES = "black blue red magenta green cyan yellow white".split()


def snaps(base):
    os.makedirs(PROBE, exist_ok=True)
    spec = Spectrum(base)
    run_script(spec, "2,3:tap,1,4:tap,3,5,>fly", PROBE)
    for door in (5, 7):
        spec = Spectrum(PROBE + "fly.z80")
        m = spec.mem
        spec.key("CAPS", True)
        end = spec.sim.registers[25] + 300 * FRAME48
        while spec.sim.registers[25] < end:
            if spec.run_tstates(end - spec.sim.registers[25], stop=32572) == 32572:
                for a, v in ((41439, door), (41441, 1), (41237 + 2 * (door - 1), 1)):
                    m[a], m[a + 1] = v & 255, v >> 8
                spec.run_tstates(4)
        spec.key("CAPS", False)
        spec.frames(600)
        room = m[41519] | m[41520] << 8
        spec.save(f"{PROBE}under{door}.z80")
        print(f"door {door}: room {room}, {PROBE}under{door}.z80")


def pace(_):
    scenes = [("outdoors, standing", "fly", [((), 300)]),
              ("outdoors, flying right through a scroll", "fly", [(("C",), 40), (("Z",), 400)]),
              ("outdoors, hovering and firing", "fly", [(("C",), 40), (("V",), 200)]),
              ("underground room 4, standing", "under5", [((), 300)]),
              ("underground room 4, walking right", "under5", [(("Z",), 300)])]
    for label, snap, seq in scenes:
        spec = Spectrum(PROBE + snap + ".z80")
        r = spec.sim.registers
        marks = []
        for keys, frames in seq:
            for k in keys:
                spec.key(k, True)
            end = r[25] + frames * FRAME48
            while r[25] < end:
                if spec.run_tstates(end - r[25], stop=PASS_MARK) == PASS_MARK:
                    marks.append(r[25])
                    spec.run_tstates(4)
            for k in keys:
                spec.key(k, False)
        d = sorted((b - a) / FRAME48 for a, b in zip(marks, marks[1:]))
        print(f"{label}: {len(d)} passes, frames a pass: min {d[0]:.2f}, "
              f"median {d[len(d) // 2]:.2f}, max {d[-1]:.2f}")


def bucket(pc):
    for lo, hi, name in [(25431, 25562, "SPRITE (25431)"), (8874, 8906, "ROM PIXEL-ADD (for SPRITE)"),
                         (3044, 3080, "ROM PO-ATTR (for SPRITE's mode 2)"), (949, 1015, "ROM BEEPER"),
                         (56, 82, "ROM interrupt and key scan"), (654, 900, "ROM interrupt and key scan"),
                         (0, 16383, "ROM, other (PRINT, colour codes)"),
                         (24600, 25591, "runtime library, other"), (25592, 41014, "compiled BASIC"),
                         (57042, 57253, "landscape scroll and print"),
                         (51675, 51699, "attribute save and restore")]:
        if lo <= pc <= hi:
            return name
    return "other machine code"


def profile(_):
    from skoolkit.simulator import Simulator
    from skoolkit.simutils import from_snapshot
    from skoolkit.snapshot import Snapshot
    for label, snap, keys, frames in [("outdoors, flying up", "fly", ["C"], 60),
                                      ("outdoors, standing", "fly", [], 300),
                                      ("underground room 4, standing", "under5", [], 300)]:
        spec = Spectrum(PROBE + snap + ".z80")
        # The Python simulator, so every instruction can be timed.
        spec.sim = from_snapshot(Simulator, Snapshot.get(PROBE + snap + ".z80"),
                                 config={"fast_djnz": False, "fast_ldir": False})
        spec.sim.set_tracer(spec)
        sim, r = spec.sim, spec.sim.registers
        mem, ops = sim.memory, sim.opcodes
        for k in keys:
            spec.key(k, True)
        c = Counter()
        end = r[25] + frames * FRAME48
        nxt = (r[25] // FRAME48 + 1) * FRAME48
        while r[25] < end:
            pc, t = r[24], r[25]
            ops[mem[pc]]()
            if r[25] >= nxt:
                if r[25] < nxt + 32 and r[26]:
                    sim.accept_interrupt(r, mem, pc)
                nxt += FRAME48
            c[bucket(pc)] += r[25] - t
        tot = sum(c.values())
        print(f"{label} ({frames} frames):")
        for k, v in c.most_common():
            print(f"  {100 * v / tot:5.1f}%  {k}")


def call(snap, addr, setup, hl=None):
    from skoolkit.simutils import PC, T
    spec = Spectrum(snap)
    m, r = spec.mem, spec.sim.registers
    setup(m)
    sp = r[12] - 2
    m[sp], m[sp + 1] = 0x00, 0x60          # return to 24576, the sentinel
    r[12], r[PC], r[26] = sp, addr, 0
    if hl is not None:
        r[6], r[7] = hl >> 8, hl & 255
    t0 = r[T]
    spec.sim.trace(addr, 0x6000, 0, t0 + 60 * FRAME48, 0, None, None, None, None, None)
    return r[T] - t0, spec


def cost(_):
    fly, under = PROBE + "fly.z80", PROBE + "under5.z80"

    def sprite(gfx, x, rows, width, mode):
        def setup(m):
            for i, v in enumerate([gfx & 255, gfx >> 8, x, 100, rows, width, mode, 0]):
                m[24783 + i] = v
        return call(fly, 25431, setup, hl=24783)[0]

    for gfx, rows, width in [(54120, 24, 3), (53730, 16, 3), (60100, 24, 2), (42450, 8, 3)]:
        for mode in (2, 0):
            print(f"SPRITE {rows}x{width} bytes, mode {mode}: x=64 {sprite(gfx, 64, rows, width, mode)} T, "
                  f"x=66 {sprite(gfx, 66, rows, width, mode)} T")

    def poke(**kv):
        return lambda m: [m.__setitem__(int(a[1:]), v) for a, v in kv.items()]

    for label, snap, addr, setup in [
            ("57042 scroll the bottom third left a character", fly, 57042, poke()),
            ("57066 scroll it right", fly, 57066, poke()),
            ("57092 scroll its attributes left", fly, 57092, poke()),
            ("57130 print column 1 (font A)", fly, 57130, poke(a23296=1, a23297=31)),
            ("57130 print column 216 (font B)", fly, 57130, poke(a23296=216, a23297=31)),
            ("57228 print the whole landscape", fly, 57228, poke(a23296=0x5E, a23297=0xE4)),
            ("45710 draw room 4", under, 45710, poke(a23296=4, a23297=5)),
            ("51687 restore the landscape's attributes", fly, 51687, poke()),
            ("52852 restore the moon's attributes", fly, 52852, poke())]:
        t = call(snap, addr, setup)[0]
        print(f"{label}: {t} T ({t / FRAME48:.2f} frames)")


def screen_stats(m, rows=range(24)):
    cells, vis, rowmax = Counter(), Counter(), {}
    for cy in rows:
        seen = set()
        for cx in range(32):
            a = m[22528 + cy * 32 + cx]
            cells[a] += 1
            on = 0
            for i in range(8):
                y = cy * 8 + i
                on += bin(m[16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2) + cx]).count("1")
            if on:
                vis[a & 7] += on
                seen.add(a & 7)
            if on < 64:
                vis[(a >> 3) & 7] += 64 - on
                seen.add((a >> 3) & 7)
        rowmax[cy] = len(seen)
    return cells, vis, rowmax


def attr_name(a):
    return (f"{NAMES[a & 7]} on {NAMES[(a >> 3) & 7]}" + (" BRIGHT" if a & 64 else "")
            + (" FLASH" if a & 128 else ""))


def report(label, results):
    cells, vis, per, rowmax = Counter(), Counter(), Counter(), Counter()
    for c, v, rm in results:
        cells += c
        vis += v
        per[len(v)] += 1
        for k, n in rm.items():
            rowmax[k] = max(rowmax[k], n)
    print(label)
    print("  cells by attribute:", ", ".join(f"{attr_name(a)}: {n}" for a, n in cells.most_common()))
    print("  pixels by colour:", ", ".join(f"{NAMES[k]}: {n}" for k, n in vis.most_common()))
    print("  colours on one screen:", ", ".join(f"{k} colours: {n} screens" for k, n in sorted(per.items())))
    print("  most colours in one character row, rows 0-23:", [rowmax[i] for i in range(24)])


def colours(_):
    land = []
    for k in range(61):
        p = 57310 + 32 * k
        _, spec = call(PROBE + "fly.z80", 57228, lambda m: (m.__setitem__(23296, p & 255),
                                                             m.__setitem__(23297, p >> 8)))
        land.append(screen_stats(spec.mem))
    report("Outdoors: the 61 landscape screens, each printed by 57228 into the flight screen", land)
    rooms = []
    for room in range(64):
        _, spec = call(PROBE + "under5.z80", 45710, lambda m: (m.__setitem__(23296, room),
                                                               m.__setitem__(23297, 5)))
        rooms.append(screen_stats(spec.mem))
    report("Underground: the 64 rooms, each drawn by 45710 into room 4's screen", rooms)
    for snap in ("fly", "under5", "under7"):
        report(f"The {snap} scene as it stands", [screen_stats(Spectrum(PROBE + snap + ".z80").mem)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["snaps", "pace", "profile", "cost", "colours"])
    ap.add_argument("--snap", default="build/cauldron.z80", help="the start for `snaps`")
    args = ap.parse_args()
    {"snaps": snaps, "pace": pace, "profile": profile, "cost": cost, "colours": colours}[args.what](args.snap)


if __name__ == "__main__":
    sys.exit(main())
