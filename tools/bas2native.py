#!/usr/bin/env python3
"""Native 6502 for the statements a pass runs most (decision 10): the
interpreter's time where it's spent.

Used by tools/bas2vm.py (--hot): a statement of stores (LET, POKE)
becomes a routine N<addr> its bytecode calls (OP_NATIVE), an IF one
NI<addr> that returns with C set when the bytecode should take its jump
(OP_NIF). Every value is a word in acc (arg for a second operand, the
6502's stack for more), with the original's semantics through the
interpreter's own routines: rt_mul, rt_div, rt_cmp, rt_rnd, and memory
by the original's addresses (dpeek_acc, peek_acc, dpoke_at, poke_at) where
the compiler can't name the place. No byte typing: what the bytecode
does, only faster. Both sides of every AND and OR are evaluated, as the
original's are.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decompile as D  # noqa: E402
from bas2vm import BLOCKS, port_place, simp  # noqa: E402


class Unsupported(Exception):
    """A statement the native backend leaves to the bytecode."""


class Native:
    def __init__(self):
        self.out = []
        self.n = 0

    def emit(self, s):
        self.out.append("    " + s)

    def label(self):
        self.n += 1
        return f"nl{self.n}"

    # ------------------------------------------------------------ expressions

    def simple(self, e):
        """(lo, hi) operands for a constant or a word at a known place."""
        e = simp(e)
        if e[0] in ("n", "c8"):
            v = e[1] & 0xFFFF
            return f"#{v & 255}", f"#{v >> 8}"
        if e[0] == "blockaddr" and D.const(simp(e[1])):
            v = BLOCKS + 8 * simp(e[1])[1]
            return f"#{v & 255}", f"#{v >> 8}"
        if e[0] == "v" or (e[0] == "dpeek" and D.const(simp(e[1]))):
            a = e[1] if e[0] == "v" else simp(e[1])[1]
            p, q = port_place(a), port_place(a + 1)
            if p and q:
                return p, q
        return None

    def expr(self, e):
        """acc = e."""
        e = simp(e)
        sm = self.simple(e)
        if sm:
            self.emit(f"LDA {sm[0]} : STA acc : LDA {sm[1]} : STA acc+1")
            return
        k = e[0]
        if k == "elemaddr":
            self.expr(e[2])
            self.emit(f"LDA #LO({e[1]}) : STA vm_w : LDA #HI({e[1]}) : STA vm_w+1 : JSR elem_calc")
        elif k == "blockaddr":
            self.expr(("bin", "+", ("bin", "*", e[1], ("n", 8)), ("n", BLOCKS)))
        elif k == "dpeek":
            self.expr(e[1])
            self.emit("JSR dpeek_acc")
        elif k == "bin":
            op = e[1]
            right = self.simple(e[3])
            if right and op in ("+", "-", "AND", "OR"):
                self.expr(e[2])
                ins = {"+": "ADC", "-": "SBC", "AND": "AND", "OR": "ORA"}[op]
                pre = {"+": "CLC : ", "-": "SEC : "}.get(op, "")
                self.emit(f"{pre}LDA acc : {ins} {right[0]} : STA acc : LDA acc+1 : {ins} {right[1]} : STA acc+1")
                return
            self.two(e[2], e[3])
            if op in ("+", "-", "AND", "OR"):
                ins = {"+": "ADC", "-": "SBC", "AND": "AND", "OR": "ORA"}[op]
                pre = {"+": "CLC : ", "-": "SEC : "}.get(op, "")
                self.emit(f"{pre}LDA acc : {ins} arg : STA acc : LDA acc+1 : {ins} arg+1 : STA acc+1")
            elif op == "*":
                self.emit("JSR rt_mul")
            elif op == "/":
                self.emit("JSR rt_div")
            else:
                self.compare(op)
        elif k == "mod":
            self.two(e[1], e[2])
            self.emit("JSR rt_div : LDA arg : STA acc : LDA arg+1 : STA acc+1")
        elif k == "un":
            op = e[1]
            if op == "PEEK":
                a = simp(e[2])
                if D.const(a) and port_place(a[1]):
                    self.emit(f"LDA {port_place(a[1])} : STA acc : LDA #0 : STA acc+1")
                    return
                self.expr(a)
                self.emit("JSR peek_acc")
                return
            self.expr(e[2])
            if op == "NEG":
                self.emit("JSR rt_neg")
            elif op == "ABS":
                self.emit("JSR rt_abs")
            elif op == "SGN":
                self.emit("JSR rt_sgn")
            elif op == "NOT":
                self.bool_of("LDA acc : ORA acc+1", "BEQ")
            else:
                raise Unsupported(op)
        elif k == "lo":
            self.expr(e[1])
            self.emit("LDA #0 : STA acc+1")
        elif k == "hi":
            self.expr(e[1])
            self.emit("LDA acc+1 : STA acc : LDA #0 : STA acc+1")
        elif k == "fx" and e[2][0] == "un" and e[2][1] == "RND":
            self.expr(e[2][2])
            self.emit("JSR rt_rnd")
        else:
            raise Unsupported(f"native {k}")

    def two(self, a, b):
        """acc = a, arg = b (b first, kept on the stack while a is made)."""
        sb = self.simple(b)
        if sb:
            self.expr(a)
            self.emit(f"LDA {sb[0]} : STA arg : LDA {sb[1]} : STA arg+1")
            return
        self.expr(b)
        self.emit("LDA acc : PHA : LDA acc+1 : PHA")
        self.expr(a)
        self.emit("PLA : STA arg+1 : PLA : STA arg")

    def bool_of(self, test, branch):
        """acc = 1 if branch is taken after test, else 0."""
        t, d = self.label(), self.label()
        self.emit(f"{test} : {branch} {t}")
        self.emit(f"LDA #0 : BEQ {d}")
        self.out.append(f".{t}")
        self.emit("LDA #1")
        self.out.append(f".{d}")
        self.emit("STA acc : LDA #0 : STA acc+1")

    def compare(self, op):
        """acc = acc op arg (signed), 1 or 0 (rt_cmp: Z equal, C acc >= arg)."""
        t, f, d = self.label(), self.label(), self.label()
        self.emit("JSR rt_cmp")
        if op == "=":
            self.emit(f"BEQ {t} : BNE {f}")
        elif op == "<>":
            self.emit(f"BNE {t} : BEQ {f}")
        elif op == "<":
            self.emit(f"BCC {t} : BCS {f}")
        elif op == ">=":
            self.emit(f"BCS {t} : BCC {f}")
        elif op == ">":
            self.emit(f"BEQ {f} : BCS {t} : BCC {f}")
        elif op == "<=":
            self.emit(f"BEQ {t} : BCC {t} : BCS {f}")
        self.out.append(f".{t}")
        self.emit(f"LDA #1 : BNE {d}")
        self.out.append(f".{f}")
        self.emit("LDA #0")
        self.out.append(f".{d}")
        self.emit("STA acc : LDA #0 : STA acc+1")

    # ------------------------------------------------------------ statements

    def store(self, dst, val, word):
        d = simp(dst)
        if D.const(d):
            p = port_place(d[1])
            if p and (not word or port_place(d[1] + 1)):
                sm = self.simple(val)
                if sm:
                    self.emit(f"LDA {sm[0]} : STA {p}")
                    if word:
                        self.emit(f"LDA {sm[1]} : STA {port_place(d[1] + 1)}")
                    return
                self.expr(val)
                self.emit(f"LDA acc : STA {p}")
                if word:
                    self.emit(f"LDA acc+1 : STA {port_place(d[1] + 1)}")
                return
        # The value into arg, the address into acc, through the translation.
        self.two(d, val)
        self.emit("JSR dpoke_at" if word else "JSR poke_at")

    def statement(self, s):
        """The routine for statement s (its lines), or Unsupported."""
        evs = s.events
        if s.kind != "ev" or not evs:
            raise Unsupported("not a plain statement")
        if all(ev[0] in ("let", "poke") for ev in evs):
            for ev in evs:
                d = simp(ev[1])
                if (D.const(d) and 24603 <= d[1] < 24759 and (d[1] - 24603) % 6 == 4):
                    raise Unsupported("a FOR's loop-back")
                v = ev[2]
                if ev[0] == "poke" and v[0] == "lo":
                    v = v[1]
                self.store(ev[1], v, ev[0] == "let")
            self.emit("RTS")
            return "store"
        if len(evs) == 1 and evs[0][0] == "if":
            ev = evs[0]
            self.expr(ev[2])
            # C set: the bytecode's jump is taken (Z: when the value is 0).
            t = self.label()
            self.emit("LDA acc : ORA acc+1")
            self.emit(f"{'BEQ' if ev[1] == 'Z' else 'BNE'} {t}")
            self.emit("CLC : RTS")
            self.out.append(f".{t}")
            self.emit("SEC : RTS")
            return "if"
        raise Unsupported("not stores or an IF")
