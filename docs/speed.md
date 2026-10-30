# Speed: the plan (2026-10-30)

Decision 6's pass is 5 frames, 200K cycles. Three agents measured the
in-flight pass (`COLON_STAR+X`) and proposed changes; what follows is
their findings, ranked, with what's done marked. Figures are their
estimates from cycle counts and models, to be measured as each lands.

## Where a pass goes

- SPRITE: 40-49% (130-187K). About 9 calls a pass (the 16x3 frames at
  shift 0, the witch 24x3, the bats 24x2). Most of the cost is per cell
  (setup about 380-537 cycles, repeated for every character row) and
  per cell-line, not per lit pixel.
- The logic: about 166K, about half of it interpreter overhead
  (dispatch, operands, the stack), about 30K memory translation.
- Erase and draw come in adjacent pairs; nothing reads pixels between
  them, except on push-scroll passes.

## SPRITE (the data and the loop)

1. Table-driven half-byte update: `new = S EOR (B AND (S OR (M AND
   nlit[S])))`, `M = O EOR (spread[glyph] AND (H EOR O))`, with 256-byte
   `hi_spread`/`lo_spread` tables. Checked exhaustively against
   `mask_of` + `half_at`. About 31-38K.
2. The cells' setup once per call, stepped per character row (+32 for
   attrs and the cell tables, +512 for the screen) instead of
   `sprite_cache` per segment. About 25K.
3. The shift fused into a column-major `seg_buf`, unrolled `LSR A : ROR
   t` chains entered by self-modified jumps, no `spr_buf` copy. About
   18-25K.
4. Small: a page lookup for `sprite_gfx`'s regions; page-aligned tables.
- Master only: per-shift tables or pre-shifted frames in a third bank.

## SPRITE (what gets drawn, and when)

- A pass-level delta pool: SPRITE's attributes at once, its pixels
  XORed into one 8-byte slot per cell, each changed cell drawn once
  (flushed before op_pass, POINT, bitmap reads, PRINT, CLS, USR). About
  38-57K before the items above; CELL_HOME's spare bits can hold the
  slot. A colour rule without state (the cell's sprite colour) would
  save more, but it's a change to decision 5: Matt's call.
- Fusing each erase with its draw: a smaller form of the same.
- A 6K shadow of the Spectrum bitmap: no room on the B; not worth it.

## The logic

1. Constant address chains folded. Done (`simp`).
2. Native regions: hot statements compiled as one flow (fall-through
   between native statements, GOSUB as JSR, NEXT native when the slot
   holds the expected loop-back), better code (folded places, inline
   signed compares, `INC v : BNE`), guarded byte-index array elements,
   bytecode dropped for statements only native code reaches. Choose by
   estimated cycles x runs (with HALT taken out of `tools/zxhot.py`'s
   counts). About 125-140K at a 4-5K native budget, the bank no bigger.
   Risks: mixed return addresses on one stack; `make vm` must enter
   native-only statements at their own labels.
3. Guarded byte-index elements in today's natives (the slot copies, 46K
   now): a subset of 2.
4. The interpreter's core (top of stack in acc, inline operands): 15-25K
   now, little after 2.
- The 16K-sideways-RAM target isn't reachable from the logic alone: its
  floor plus the data bank is well over 16K.
