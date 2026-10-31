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

1. (Done.) Table-driven half-byte update: `new = S EOR (B AND (S OR (M AND
   nlit[S])))`, `M = O EOR (spread[glyph] AND (H EOR O))`, with 256-byte
   `hi_spread`/`lo_spread` tables. Checked exhaustively against
   `mask_of` + `half_at`. About 31-38K.
2. (Done, per character row.) The cells' setup once per call, stepped per character row (+32 for
   attrs and the cell tables, +512 for the screen) instead of
   `sprite_cache` per segment. About 25K.
3. (Done.) The shift fused into a column-major `seg_buf`, unrolled `LSR A : ROR
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
2. Native regions (chaining done: OP_NGO, G<addr>; the better code and
   the selection to come): hot statements compiled as one flow (fall-through
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

## Against the original (2026-10-30)

`tools/passtime.mjs` reports each pass's work as well (to `op_pass`,
before the wait for the pace; `PASSTIME_ALL=1` lists them). The
original's passes, measured the same way on the Z80 (keys held from the
third pass; frames at 69888 T-states):

| Run | The original | The port's work |
|---|---|---|
| standing | median 5.25 frames, max 7.3 | median 141K cycles (2.8 frames), max 300K |
| flying right | median 6.1, max 8.0 | median 186K (3.7), max 369K (7.4) |
| flying and firing | median 7.8 (`runtime.md`) | median 210K (4.2), max 369K |

So at decision 6's 5 frames the port is as fast as the original standing
and faster in flight; the passes that overrun it are the original's
slow passes too (more monsters, the spikes every few passes), and still
quicker than the original's.

## Later in flight (2026-10-30)

Over a longer flight the monsters accumulate, and passes 30-55 of a
flight up and right sat over the pace: SPRITE nearly half their work.
Three steps took their median work from about 227K cycles to about
201K, the pace itself (measured with an exact per-pass profile, the
same run each time):

1. Cells with no scenery, or scenery in the sprite's own colour (nearly
   all of them), take a plain loop: M is the sprite's own colour, so
   the scenery's glyph and colour aren't read per line (`blank_glyph`).
2. `seg_row` does a segment's rows in one call.
3. Unshifted rows, the most common, are copied by a loop unrolled for
   the sprite's width.

The passes still well over the pace are mostly the sound: BEEPER's
chirps stop the game while they play, as the original's do (decision
8). Printing the score's divides now skip a small dividend's empty top
byte.

Pass times vary from build to build with the monsters RND brings, since
a pass's timing moves the seed; compare builds on the same profile run,
not on single passtime runs.
