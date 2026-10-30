# Decisions

Every call the port makes that the original didn't, numbered, with the
date and the reason. Nothing is changed from the original quietly.
**Provisional** marks a call made while Matt was away, for their review:
it stands until they say otherwise, and the options are kept beside it.

## 1. The original is Palace's Spectrum release (2026-10-30)

The specification is Palace Software's 48K Spectrum *Cauldron* as ZXDB
entry 850's TAP holds it (`original/README.md`): its code, run headless
on SkoolKit, is the oracle for every layer. The TZX holds the same game
and screen blocks. Silverbird's re-release isn't used.

Targets (Matt, 2026-10-30): a Model B with 16K of sideways RAM, and the
Master 128, from one disc.

## 2. MODE 1 in the Spectrum's geometry (2026-10-30, provisional)

The screen is MODE 1's pixels with the CRTC narrowed to 256 x 192, the
Spectrum's geometry exactly, as in CE2 and nm: 12K at the top of main
RAM, a character row 512 bytes.

The alternative was MODE 2, which keeps all eight colours at half the
width. `tools/colourstudy.py` counts it on the original's own pixels
(the landscape's columns and the rooms' blocks, both proven against the
original's drawing by `tools/zxgfx.py --check`): 13% of the landscape's
lit pixels and 17% of the rooms' are half of a pair that is half unlit,
which MODE 2 must lose or widen. The art is fine detail (dithered trees,
brickwork), as nm's was. MODE 1's cost is colour, which decision 3 keeps
almost whole.

## 3. Colour: a palette per band, chosen per screen and per room (2026-10-30, provisional)

The original's paper is black everywhere and its colour is one ink per
8 x 8 cell, BRIGHT or not (`docs/research/graphics.md`). The BBC has no
BRIGHT, so BRIGHT and normal inks of one colour are one colour.

MODE 1 gives black and three inks. The screen falls into bands that
the original keeps apart: the panel (rows 0-3), the sky (rows 4-15) and
the landscape (rows 16-22) outdoors, the room (rows 3-22) underground.
Each band gets its own three inks, set by palette splits in the
interrupt (as in CE2, decision 15 there). The landscape is shown a
screen at a time (the push scroll, graphics.md) and the rooms one at a
time, so their palettes are chosen per landscape screen and per room,
offline, from the original's pixels.

What it keeps, as `tools/colourstudy.py` counts lit pixels shown in their
own colour (2026-10-30):

| | One palette a screen or room | Two inks, one colour kept for sprites | A palette per character row |
|---|---|---|---|
| The landscape | 99.33% | 96.61% | 99.90% |
| The rooms | 100% | 96.59% | 100% |

Open, to settle with the sprites' layer: how the sprites are coloured.
The original turns the cells a sprite covers to its colour outdoors
(the witch cyan), and underground colours only background cells, so a
sprite's colour depends on the band it's in. Keeping one logical colour
for sprites costs the figures in the second column; drawing sprites in
whichever logical colour is nearest in each band costs nothing in the
background. The panel needs five colours with four at most in any one
row, so it may take a split a row. And during the push scroll two
landscape screens are on view at once: their palettes may not agree.

## 4. The splits: one logical colour each, cyan kept for sprites (2026-10-30, provisional)

How decision 3's bands are split. A split can change one logical colour
cleanly: its four palette entries are four writes, 16us, inside the
32us horizontal blank. So the bands are laid out for each split to
change one, and each logical colour to change only where nothing on
the line above or below shows it:

| Split | Lands before | Changes |
|---|---|---|
| VSync | row 0 | all sixteen: logical 1 yellow, 2 magenta, 3 green |
| 0 | row 1 | logical 2 cyan |
| 1 | row 2 | logical 2 magenta |
| 2 | row 3 | logical 2 cyan |
| 3 | row 3, line 4 | logical 3: the sky's white, or the room's (row 3 shows only yellow and cyan) |
| 4 | row 4 | logical 1: the landscape's or the room's (the sky shows none of logical 1) |
| 5 | row 16 | logical 3: the landscape's |

The panel uses four inks, at most three in a row (`graphics.md`, and the
flight snapshot's rows: magenta and yellow; green, cyan and yellow;
magenta, green and yellow; cyan and yellow). The sky uses white and the
sprites' cyan.

**Cyan is logical 2 everywhere below the panel.** It is the colour the
original turns the cells under the witch and the bats outdoors (the
clash, `graphics.md`), the witch's colour underground, and every room
has cyan in it. So the sprites have their colour in every band without a
split, and the landscape and rooms keep two inks of their own besides.
What it costs, as `tools/colourstudy.py`'s counts give it (lit pixels in
their own colour): the landscape 98.36% (99.33% with three free inks),
the rooms 100%. Which inks go where is `tools/mkdata.py`'s, checked
whole by `make draw`.

The splits' timing was swept with `tools/splitsweep.py` (2026-10-30):
clean from 88 to 116 on the B and the Master, parked at 102 in the middle.
`make splits` checks it each time.

Still open (D6 in `docs/brief.md`): the enemies' own colours underground
(white, red, green) in rooms that already have two inks besides cyan.

## 5. No colour clash (Matt, 2026-10-30)

The original's SPRITE recolours every cell a sprite covers: outdoors the
witch turns a tree's cells cyan, underground an enemy takes over the
background cells it crosses (`graphics.md`). Matt prefers the port
without the clash.

The game logic reads both things the clash touches, so neither can
simply go:

- **The attributes.** The logic tests them (the grass's 65 under a
  landing, 27424). The port keeps the Spectrum's attribute file as a
  shadow (`attrs`), and SPRITE changes it by its modes exactly as the
  original does; it just no longer colours anything.
- **The lit pixels.** The logic's POINT reads them (the trees beside the
  witch, 27498). The port's SPRITE XORs exactly the original's pixels,
  so lit and unlit are the original's everywhere.

Only the colour of a lit pixel is the port's own. Each cell remembers
the glyph and colour its scenery drew there (pages 4-12, `draw.6502`);
when SPRITE's XOR lights a pixel, it takes the scenery's colour if the
scenery has it lit (a pixel coming back from under a sprite), the
sprite's own colour if not; a lit pixel the XOR leaves lit keeps its
colour, and one it clears goes black. A sprite's own colour is the ink
its mode would have given the cell (the block's attribute in mode 0,
ATTR_P in mode 1, ATTR_T in mode 2), through its row's band (decision 4).
So the witch is cyan over a tree, the tree stays green around her, and
where they overlap the XOR leaves a hole, as on the Spectrum.

`make sprites` checks it: random calls of SPRITE on the original's
scenes (graphics, places, modes, rows past column 31, draws and erases)
run on the original and on the port. The attributes must be the
original's; the pixels follow a model of SPRITE's XOR through the
Spectrum's own screen addresses, which must leave exactly the original's
lit pixels, coloured by the rule above.

What it can get wrong: where two sprites overlap and one is erased, the
other's pixels that come back take the erasing call's colour (outdoors,
the erase's ATTR_T is white).

## 6. The pace: a fixed pass length (Matt, 2026-10-30)

The original has no frame sync: a pass of its main loop takes as long as
a 3.5MHz Z80 took over it, 4-8 frames, slower with more sprites
(`runtime.md`: medians 5.25 frames standing and 7.77 firing outdoors,
3.92 underground). A BBC running flat out would run at its own speed.
The port waits for VSync to start each pass at a fixed length from the
original's medians: 5 frames above ground, 4 below. To tune against the
original's play once the game runs; a pass that overruns starts the
next at once.

## 7. The push scroll at the original's pace (Matt, 2026-10-30)

The push (32 steps, the game stopped, `graphics.md`) stays as the
original's design, a step every 2.3 frames as measured; on the BBC a
step on VSync, alternating 2 and 3 frames. Hardware scrolling can't move
a third of the screen alone.

## 8. Sound: the chirps as tones (Matt, 2026-10-30)

BEEPER's chirps become SN76489 tones at BEEPER's pitches, a tone a step
at the step's length, with the game stopped while they play, as the
original's is. The menu's click is a short tone.

## 9. Controls (Matt, 2026-10-30)

The original reads Kempston, Sinclair II or the keys CAPS SHIFT to V
(left, right, up, down, fire). The port's are the usual BBC ones (Matt):
**Z** left, **X** right, **:** up, **/** down, **RETURN** fire, as CE2's
are (in jsbeeb on a PC keyboard, : is the ' key); redefinable, and an
analogue joystick.

## 10. The logic: the original's BASIC compiled again, to bytecode (2026-10-30, provisional)

The original's game logic is integer BASIC compiled to Z80
(`docs/research/compiler.md`), and `tools/decompile.py` recovers every
statement as expression trees, each checked against the Z80 running it.
So instead of transcribing 1345 statements by hand, the port compiles
the same program again, for the 6502: `tools/bas2vm.py` turns the trees
into bytecode for a small interpreter (`src/vm.6502`), with the
original's library's own semantics (`src/basrt.6502`: the multiply's
leaking carry, the divide's signs, RND). It is the original's decision
(a compiled BASIC program) ported, and exact by construction:
`make vm` runs every statement the interpreter can on py65's 6502 and on
the original's Z80 from the same random state, and they must agree on
every byte of the variables, the FOR slots, the sprite blocks and the
seed, and on where they go next.

Why bytecode (figures from 2026-10-30): compiled natively (each node to
6502, bytes where the measured ranges allow, `tools/zxranges.py`) the
program is 18.4K, threaded (a JSR an operation) about 20.4K; as bytecode
9.9K, with an interpreter of about 1.5K. The original's own is 15.4K of
Z80. The B with 16K of sideways RAM has room for none of the first two.

What it costs is time: an operation's dispatch is about 37 cycles, a
pass of the original's main loop runs about 1100 statements (in flight,
measured), so a pass of pure bytecode may not fit decision 6's 5 frames
with the sprites. Matt (2026-10-30): optimisations come later, space and
time. The way is open: the same compiler can emit native or threaded
code for the statements a pass runs most (201 distinct in flight), and
fuse common sequences of operations.

The variables keep the original's layout, so the port's and the
original's can be compared word for word, pass by pass.

## 11. Two sideways RAM banks, for now (2026-10-30, provisional)

The game now needs two banks: the drawing's data (CAULDAT: the fonts,
the landscape, the rooms) in one, the compiled BASIC and its tables
(CAULLOG) in the other, with the code, the interpreter and the sprites
in main RAM. That is a Model B with 32K of sideways RAM, or a Master.
Decision 1's target was 16K: it doesn't fit as things stand (the
build's `PRINT`s give each part), and fitting it is part of the
optimisation Matt put off until the game works (decision 10): fusing
the bytecode's common sequences, packing the landscape's columns and the
colour maps, computing what tables hold now. If that falls short, the
choice is Matt's: 32K, or a disc-streaming edition as CE2S was.

LOADER fills the banks before CAULDRN loads (it stages each file where
CAULDRN will load), and the interpreter keeps the logic's bank paged in;
whatever draws pages the data's in for the time it takes.
