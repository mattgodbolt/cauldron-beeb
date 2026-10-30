# The runtime: library, frame and sound

Everything below the compiled BASIC: the compiler's runtime library, the
hand-written machine code the BASIC calls with `USR`, how the game paces
itself and how it makes sound. Addresses are decimal, the original's.
`disasm/runtime.ctl` labels all of it (`make disasm`); graphics.md covers
drawing and colour, data.md the memory map. The compiled code's own
idioms, and the library from the compiler's side, are in compiler.md.

Measurements are quoted with the command that made them;
`tools/zxprobe.py snaps` makes the scenes they run in (`build/probe/`).

## The runtime library (24823-25591)

The TAP calls 24600, a `JP 25592` to the first compiled statement. Between
them the compiler keeps its workspace (zero on the tape, so nothing here
is initialised data):

- **24603-24758:** FOR-NEXT control blocks. Each compiled FOR writes its
  limit, step and loop-back address (a word each) to its own fixed slot,
  and its NEXT reads them back (for example 24741/24743/24745 for the
  first loop at 25612).
- **24759-24822:** eight sprite parameter blocks of 8 bytes for SPRITE
  (below), block n at 24759+8n.

The library proper, routine by routine. "True" is 1 and "false" 0
throughout; every routine takes its operands in HL (left) and DE (right)
and answers in HL.

| Address | Routine | Contract |
|---|---|---|
| 24823 | DRAW | HL=dx, DE=dy, signed: splits each into magnitude and sign (C/E, B/D) and calls ROM DRAW-LINE (9402), saving H'L' around it. |
| 24860 | recolour | B=bits to set, C=bits to replace: every attribute (22528, 768 of them) becomes `(a AND NOT C) OR B`. |
| 24880 | multiply | HL=HL*DE, 16-bit shift-and-add after RT_SIGNS makes both positive; negated at the end if one was negative. |
| 24911 | divide | HL=HL/DE, DE=the remainder, restoring division over 17 steps; a divisor of 0 returns 0 rather than an error. |
| 24972 | negate | HL=-HL (CPL both bytes, INC). |
| 24980 | `=` | HL=1 if HL=DE. Leaves Z from the SBC, which 24998 relies on. |
| 24989 | `<>` | |
| 24998 | `>=` | Swaps, tests equality, else falls into `<`. 24999 is `<=`. |
| 25008 | `<` | Signed: SBC HL,DE, the sign bit corrected by the overflow flag (JP PO), into HL by ADC HL,HL. |
| 25023 | `>` | Swaps and does `<`. |
| 25026 | INKEY$ | ROM KEY-SCAN (654), K-TEST (798), K-DECODE (819): HL=the code or 0. Used only by the menu. |
| 25048 | PEEK | |
| 25051 | IN | Port BC=HL. Used only by the menu, for the Kempston port (31). |
| 25057 | signs | For multiply and divide: A counts the negative operands, each made positive (25063 does HL alone). |
| 25073 | POINT | L=x, E=y: ROM PIXEL-ADD (8874), the pixel shifted down to bit 0. |
| 25089 | ATTR | L=line, E=column. |
| 25106 | SCREEN$ | Compares the cell with the 96 glyphs at CHARS+256, plain or inverse: HL=the code or 0. |
| 25173, 25180 | AND, OR | Bitwise on 16 bits. |
| 25187 | NOT | HL=1 if HL=0, else 0. |
| 25195 | SGN | |
| 25205 | USR | Calls HL and returns BC in HL. Every hand-written routine is reached this way (HL is often computed: the scroller keeps its routines' base, 56900, in a variable). |
| 25212 | | A lone RET the compiled code calls once, an empty statement. |
| 25214 | RND | `seed = (seed+1)*77`, made 78 if that is 0, less 1, with the signed multiply (24880). The seed is kept in DEFADD (23563), seeded from FRAMES with bit 15 cleared at start-up (25598). HL=the new seed divided by the argument with the signed divide (24911), the remainder: RND(10) after seeds 100 and 30000 gives 6 and 9, but 0 after 40000 and 65000 (the seed is then negative). A port must transcribe both routines for the sequence to match. |
| 25244 | | Powers of ten (10000, 1000, 100, 10) for 25252. |
| 25252 | PRINT n | HL as signed decimal through RST 16, without leading zeros. |
| 25310 | INPUT | The ROM editor (3884) with ERR-SP pointing at a recovery; BC=the number, 0 on an error. Not reached in play. |
| 25380 | trace | Prints `[line]` at row 0, column 25 of the lower screen and stops with report L on BREAK. Not reached in play. |
| 25416 | BEEP | Stacks HL (the pitch) as a small integer above the duration the compiled code has stacked, and calls ROM BEEP (1016). |
| 25431 | SPRITE | Below. |
| 25563 | IM 2 set-up | Vector at 65279 to 25576, IM 2. Never called: the game runs in IM 1 throughout. |
| 25576 | IM 2 handler | Calls the address patched into 25583 (0 on the tape) and joins the ROM's handler at 58. |

The arithmetic and comparisons are all 16-bit signed integers; there is
no floating point in the compiled code except the menu's `BEEP .1,n`,
which builds its duration with the ROM calculator (39950).

## SPRITE (25431)

The one sprite routine. HL points at an 8-byte parameter block:

| Offset | |
|---|---|
| 0-1 | The graphic's address |
| 2 | x, 0-255 |
| 3 | y in PLOT coordinates: 175 is the top pixel row, 0 the bottom of the upper screen |
| 4 | Rows |
| 5 | Width in bytes |
| 6 | Attribute mode: 0, 1 or 2 |
| 7 | Attribute |

**The graphic** is `rows * width` bytes, row by row from the top, one bit
a pixel, MSB leftmost; no mask. Animation frames of a set follow each
other in memory (data.md lists them).

**Per pixel row**, from y down to y-rows+1:

1. ROM PIXEL-ADD (8874) with B=y, C=x gives the screen address and
   x mod 8. Recomputed for every row.
2. **The attributes of the row's cells** are set, for `width` cells, or
   `width+1` when x mod 8 is not 0. The attribute address is formed from
   the screen address (`H = ((H >> 3) AND 3) OR 88`), so this too is
   repeated for every one of the cell's 8 pixel rows:
   - mode 0: if the cell's attribute equals ATTR-P (23693), it becomes
     the block's attribute. A sprite colours only background cells.
   - mode 1: if it equals the block's attribute, it goes back to ATTR-P.
     The erase for mode 0.
   - mode 2: the ROM's print colours: PO-ATTR (entered at 3044, after its
     address calculation) applies ATTR-T, MASK-T and P-FLAG. With
     MASK-T 0, as in play, the cell simply becomes ATTR-T.
3. **The row's pixels are XORed onto the screen.** At x mod 8 = 0, byte
   by byte. Otherwise each byte goes into a 16-bit HL, shifted left by
   `8 - x mod 8` with an ADD HL,HL loop, and its two halves are XORed
   into the screen byte and the next, so a row writes `width+1` bytes.

**Drawing and erasing are the same call.** The compiled code draws a
sprite with one block (24767, say) and erases it, before moving it, with
a second block holding the same graphic and position (24775) and a
different attribute set-up. XOR leaves the background intact where they
cross; the attribute modes decide the colours (graphics.md, "Colour").

**No clipping.** The next byte after column 31 is the next line's
column 0 (and its attribute the next cell's): nothing keeps a sprite on
screen but the compiled code's limits. A y above 175, or a row walking
below 0, makes PIXEL-ADD stop the program with report B.

**Cost** (`tools/zxprobe.py cost`, T-states for one call):

| Sprite | Mode | x a multiple of 8 | x not |
|---|---|---|---|
| 24 rows x 3 bytes | 2 | 32759 | 54311 |
| 24 rows x 3 bytes | 0 | 24017 | 42641 |
| 16 rows x 3 bytes | 2 | 21871 | 36239 |
| 24 rows x 2 bytes | 2 | 24623 | 41255 |
| 8 rows x 3 bytes | 0 | 8055 | 14263 |

So a witch drawn and erased at an odd x costs about 1.5 frames of
69,888 T-states. Most of it is overhead per row: PIXEL-ADD, the
attribute pass repeated for each of a cell's 8 rows, and the shift loop
(up to 7 ADD HL,HL per byte).

## The hand-written machine code

All of it is called by `USR`, with its parameters POKEd into the printer
buffer: (23296) and (23297), as two bytes or as one word. The control
reader returns its results in 23728 and 23729, two system variables a
48K doesn't use.

| Address | Routine | Called |
|---|---|---|
| 42140 | Print the ending text (42169) with the panel font | at the end of a won game |
| 45710 | Draw an underground room ((23296)=room, (23297)=background attribute) | on entering a room |
| 50350 | Print the game-over text (50388) with the panel font | |
| 50369 | Print the menu (50550) | the menu |
| 50762, 50768, 50775 | Open stream 2; CHARS=55874; CHARS=15360 | by the above |
| 51675 | Save the attributes of character rows 16-21 to 51700 | after the landscape is printed |
| 51687 | Restore them | every pass outdoors |
| 51900 | Read the controls | every pass |
| 52852 | Restore the moon's attributes (52820, 5 x 6 to rows 7-11, columns 6-11) | every pass outdoors |
| 55565 | Print the moon and stars, then the panel; 55567 the cottage's scrolls then the panel; 55569 the panel alone | on a change of scene |
| 57042, 57066 | Scroll character rows 16-23 a character left, right | per scroll step |
| 57092, 57111 | Scroll their attributes left, right | per scroll step |
| 57130 | Print a landscape column ((23296)=id, (23297)=screen column) | per scroll step |
| 57228 | Print the whole landscape ((23296)=its map address) | on arriving outdoors |

Not reached: 56964 and 57005 scroll the landscape 4 pixels with RLD and
RRD (base 56900 + 64 and + 105, where the 8-pixel routines are + 142 and
+ 166), and 56933 is the tail of a 1-pixel scroll whose head the PEEK
list at 56920 has overwritten. The scroller was a finer one once.

**The controls (51900).** (23296) is the method the menu chose: 0
Kempston (IN 31), 1 Sinclair 2 (52088), 2 keys (IN 254 with A=254, the
CAPS SHIFT to V half-row). A combination is matched whole against a
list of values and gives the direction in 23728: 0 none, 1 up, 2
up-right, 3 right, 4 down-right, 5 down, 6 down-left, 7 left, 8 up-left.
Fire sets 23729 to 1. With the keys: C up, X down, CAPS SHIFT left, Z
right, V fire; up-right is Z with C, and so on. A combination not in the
list (three keys, or left with right) reads as no direction.

## The frame

**No HALT and no wait in the main loop.** The game runs flat out; the
only pauses are ROM PAUSE calls in set pieces (`PAUSE 5` on going through
a door, 32747; `PAUSE 1` at 32918 and 33697). The ROM's IM 1 interrupt
runs as usual (FRAMES, the keyboard scan), and costs a little under 2%.

Passes, timed from one call of the control reader (29505, which USRs
51900, once a pass) to the next (`tools/zxprobe.py pace`):

| Scene | Frames a pass: min | median | max |
|---|---|---|---|
| Outdoors, standing | 4.82 | 5.25 | 7.26 |
| Outdoors, flying right through a scroll | 3.69 | 4.56 | 80.81 |
| Outdoors, hovering and firing | 5.89 | 7.77 | 10.20 |
| Underground room 4, standing | 3.77 | 3.92 | 3.97 |
| Underground room 4, walking right | 3.00 | 4.11 | 70.67 |

So the game moves at roughly 10 passes a second, slowing as more
sprites are on screen; each pass moves the witch 2 pixels on foot and 8
in flight. The long passes are the scroll (32 steps of 2.3 frames, see
graphics.md) and drawing a new room (45710, 5.55 frames for room 4, plus
the panel and objects). The game logic does not run during either.

Where the time goes (`tools/zxprobe.py profile`, share of T-states):

| | Outdoors, flying | Outdoors, standing | Underground |
|---|---|---|---|
| SPRITE (25431) | 38.8% | 39.6% | 35.3% |
| ROM PO-ATTR, for SPRITE's mode 2 | 12.6% | 11.6% | - |
| ROM PIXEL-ADD, for SPRITE | 4.6% | 5.4% | 4.7% |
| Compiled BASIC | 25.4% | 24.0% | 37.0% |
| Runtime library, other | 11.5% | 11.6% | 21.7% |
| ROM, other (PRINT, colour codes) | 3.3% | 4.0% | - |
| ROM interrupt and key scan | 1.7% | 1.3% | 1.3% |

Sprites take over half the time outdoors. The ROM time the earlier
sampling put "in PRINT" (0B00-0BFF) is almost all PO-ATTR at 3044
(0BE4), which SPRITE's mode 2 calls for each pixel row of each cell;
the game prints little in play.

## Sound

**Beeper only, through the ROM.** Every OUT to port 254 in play is in the
ROM's BEEPER (the OUT at 993), apart from one BORDER (8859). No routine
of the game's own drives the speaker. The sound blocks the game while it
plays.

There are three kinds:

- **A rising chirp** (32194): `FOR p=200 TO 100 STEP -5: BEEPER(DE=1, HL=p)`.
  21 calls, each giving two cycles of half-period `4p + 118` T-states, so
  from about 1900 Hz to 3380 Hz. 16.1 ms in all (measured from the port
  log). Called from 33572, 33617, 34859, 36474 and 39163; seen when the
  witch shoots something (34859).
- **A falling chirp** (32265): `FOR p=200 TO 300 STEP 5`, about 1900 Hz
  down to 1320 Hz, 23.3 ms. Called from 30247, 34763 and 39245; 34763
  plays when the witch is hit and loses magic.
- **The menu's click** (39950): `BEEP .1, n` through 25416 and ROM BEEP,
  as an option is chosen.

The half-period figure is BEEPER's own (each DE=1 call makes 4 edges,
3 at the half-period and one stretched by the loop); the edges come from
`tools/zx.py --ports`. For the BBC: a chirp is 21 short tones of
falling or rising period, one call to the SN76489 a step, or a User VIA
timer toggling a tone channel's volume to keep the two-cycle grain.
