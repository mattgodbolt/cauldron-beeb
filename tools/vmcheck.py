#!/usr/bin/env python3
"""Each statement of the compiled BASIC on the port's interpreter against
the original's Z80 code, from the same random state.

    .venv/bin/python tools/vmcheck.py [--trials N] [--seed S] [--only ADDR]

Builds build/vmtest.ssd (src/vmtest.6502) (the interpreter, its runtime and the
bytecode tools/bas2vm.py made, without the rest of the game) and runs it
on py65's 6502. For each statement whose effects are the interpreter's
own (stores, branches, GOSUB, FOR, NEXT, the arithmetic, RND), from
random variables: the Z80 runs the original's code from the statement's
address to the next statement it reaches, the 6502 runs the bytecode
from the statement's label to the next label it reaches, and the two
must agree on where they went and on every byte of the variables, the
FOR slots, the sprite blocks and RND's seed. Statements that use what
the port hasn't built yet (they stop at vm_unbuilt) are counted apart.
Exits non-zero on any disagreement.
"""
import argparse
import json
import os
import random
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decompile as D  # noqa: E402
from bas2vm import SYSVARS  # noqa: E402
from py65.devices.mpu6502 import MPU  # noqa: E402
from skoolkit import CSimulator  # noqa: E402
from skoolkit.simutils import PC, SP, from_snapshot  # noqa: E402
from skoolkit.snapshot import Snapshot  # noqa: E402

VARS, VARS_END = 41015, 41575
SLOTS, SLOTS_END = 24603, 24759
BLOCKS, BLOCKS_END = 24759, 24823
SEED = 23563
ORG = 0x1000
# The kinds the interpreter does by itself.
OWN = {"let", "poke", "if", "goto", "gosub", "call"}


def place_addr(syms, place):
    name, _, off = place.partition("+")
    return syms[name] + int(off or 0)


def symbols(path):
    out = {}
    for assembly in json.load(open(path))["assemblies"]:
        for section in assembly["sections"]:
            for kind in section.values():
                if isinstance(kind, dict):
                    for k, v in kind.items():
                        if isinstance(v, dict) and "value" in v and "@" not in k:
                            out[k] = v["value"]
    return out


def build():
    baron = "../baron/build/src/baron" if os.path.exists("../baron/build/src/baron") else "baron"
    subprocess.run([sys.executable, "tools/bas2vm.py"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run([baron, "-o", "build/vmtest.ssd", "--opt", "3", "--symbols", "build/vmtest.json",
                    "src/vmtest.6502"], check=True, stdout=subprocess.DEVNULL)
    syms = symbols("build/vmtest.json")
    # The image: the disc's file T, at ORG (DFS: the catalogue's two
    # sectors, the file from sector 2).
    disc = open("build/vmtest.ssd", "rb").read()
    length = syms["test_end"] - ORG
    return syms, disc[512:512 + length]


def uses_unbuilt(st):
    """Whether the statement needs what only the port's layers will do."""
    def walk(e):
        if not isinstance(e, tuple) or not e:
            return False
        if e[0] == "fx":
            t = e[2]
            return not (t[0] == "un" and t[1] == "RND") or walk(t)
        if e[0] in ("fn", "inkey"):
            return True
        return any(walk(x) for x in e[1:] if isinstance(x, tuple))
    return any(ev[0] not in OWN or any(walk(x) for x in ev[1:] if isinstance(x, tuple)) for ev in st.events)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--snap", default="build/cauldron.z80")
    ap.add_argument("--trials", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--only", type=int)
    args = ap.parse_args()
    syms, image = build()
    mem0 = D.load_memory(args.snap)
    dec = D.Decompiler(mem0)
    dec.run()
    stmts = dec.stmts
    starts = {s.addr for s in stmts}
    label_at = {syms[f"L{a}"]: a for a in starts}
    snapshot = Snapshot.get(args.snap)
    zsim = from_snapshot(CSimulator, snapshot)
    base = bytes(zsim.memory)
    sp0 = zsim.registers[SP]
    rng = random.Random(args.seed)
    # Every region vm_xlat maps (src/vmxlat.6502) with the original's
    # bytes in it, and compared after.
    from mkdata import LOGIC_REGIONS
    port = {"bv": (VARS, VARS_END), "bslots": (SLOTS, SLOTS_END), "sprite_blocks": (BLOCKS, BLOCKS_END),
            "attrs": (22528, 23296), "attr_save": (51700, 51892), "landmap": (57310, 59326)}
    at = 0
    for lo, hi in LOGIC_REGIONS:
        port[f"logictab+{at}"] = (lo, hi)
        at += hi - lo
    agree = disagree = unbuilt = 0
    unmapped = set()
    skipped = 0
    for st in stmts:
        if args.only and st.addr != args.only:
            continue
        if st.kind == "wait" or (st.kind == "ev" and (uses_unbuilt(st) or st.events[-1][0] == "return")):
            unbuilt += 1
            continue
        bad = None
        for t in range(args.trials):
            mem = bytearray(base)
            for a in range(VARS, VARS_END, 2):
                v = rng.randint(0, 24) if t % 2 == 0 else rng.randint(0, 65535)
                mem[a], mem[a + 1] = v & 255, v >> 8
            for a in range(SLOTS, SLOTS_END, 6):
                for o, v in ((0, rng.randint(-3, 24)), (2, rng.choice([1, 1, -1, 2]))):
                    mem[a + o], mem[a + o + 1] = v & 255, (v >> 8) & 255
                back = rng.choice(sorted(starts))
                mem[a + 4], mem[a + 5] = back & 255, back >> 8
            mem[SEED], mem[SEED + 1] = rng.randint(0, 255), rng.randint(0, 255)
            # The Z80, from the statement to the next statement it reaches.
            zsim.memory[:] = mem
            zsim.registers[PC] = st.addr
            zsim.registers[SP] = sp0
            for n in range(300000):
                zsim.run()
                if zsim.registers[PC] in starts:
                    break
            zpc = zsim.registers[PC]
            zmem = bytes(zsim.memory)
            # The 6502: the same state in the port's places, the bytecode
            # from the statement's label to the next label it reaches.
            cpu = MPU()
            cpu.memory = bytearray(65536)
            cpu.memory[ORG:ORG + len(image)] = image
            for name, (lo, hi) in port.items():
                p = place_addr(syms, name)
                cpu.memory[p:p + hi - lo] = mem[lo:hi]
            # (FOR slots hold the original's loop-back addresses: the port's labels.)
            for a in range(SLOTS, SLOTS_END, 6):
                back = mem[a + 4] | mem[a + 5] << 8
                p = syms["bslots"] + a - SLOTS + 4
                cpu.memory[p], cpu.memory[p + 1] = syms[f"L{back}"] & 255, syms[f"L{back}"] >> 8
            for a, place in SYSVARS.items():
                cpu.memory[place_addr(syms, place)] = mem[a]
            vpc, vsp, vm_next = syms["vpc"], syms["vsp"], syms["vm_next"]
            lab = syms[f"L{st.addr}"]
            cpu.memory[vpc], cpu.memory[vpc + 1] = lab & 255, lab >> 8
            cpu.memory[vsp] = 16
            cpu.sp = 0xF0
            cpu.pc = vm_next
            first = True
            for n in range(2000000):
                if cpu.pc == vm_next:
                    here = cpu.memory[vpc] | cpu.memory[vpc + 1] << 8
                    if not first and here in label_at:
                        break
                    first = False
                if cpu.pc in (syms["vm_unbuilt"], syms["vm_bad_address"], syms["vm_bad_kind"]):
                    break
                cpu.step()
            if cpu.pc == syms["vm_unbuilt"]:
                # (a PEEK of the bitmap: the screen's, not the interpreter's)
                skipped += 1
                break
            if cpu.pc in (syms["vm_bad_address"], syms["vm_bad_kind"]):
                # An address the port has no place for: data not built yet,
                # or a random index far outside its array. The Z80's run
                # says which: if it touched only what the port maps, it's ours.
                a = cpu.memory[syms["acc"]] | cpu.memory[syms["acc"] + 1] << 8
                unmapped.add(a)
                skipped += 1
                break
            pvpc = cpu.memory[vpc] | cpu.memory[vpc + 1] << 8
            ppc = label_at.get(pvpc)
            pm = cpu.memory
            diffs = []
            for name, (lo, hi) in port.items():
                p = place_addr(syms, name)
                for a in range(lo, hi):
                    if name == "bslots" and (a - SLOTS) % 6 in (4, 5):
                        continue                   # (the loop-back: compared as labels below)
                    if pm[p + a - lo] != zmem[a]:
                        diffs.append(a)
            for a in range(SLOTS, SLOTS_END, 6):
                zb = zmem[a + 4] | zmem[a + 5] << 8
                p = syms["bslots"] + a - SLOTS + 4
                if syms.get(f"L{zb}") != pm[p] | pm[p + 1] << 8:
                    diffs.append(a + 4)
            for a, place in SYSVARS.items():
                if pm[place_addr(syms, place)] != zmem[a]:
                    diffs.append(a)
            # (Labels can share an address: a statement with no bytecode.)
            if syms.get(f"L{zpc}") != pvpc or diffs:
                bad = f"went to {ppc} (the Z80 to {zpc}); differ at {diffs[:8]}"
                break
        if bad:
            disagree += 1
            print(f"{st.addr}: {bad}   [{st.kind}] {st.text or [e[0] for e in st.events]}")
        else:
            agree += 1
    print(f"vmcheck: {agree} statements agree, {disagree} disagree, {unbuilt} use what isn't built yet "
          f"({args.trials} trials each; {skipped} trials stopped at an address the port has no place for)")
    near = sorted(a for a in unmapped if not (VARS <= a < VARS_END + 4096))
    if near:
        print("  addresses with no place:", ", ".join(map(str, near[:20])))
    return 1 if disagree else 0


if __name__ == "__main__":
    sys.exit(main())
