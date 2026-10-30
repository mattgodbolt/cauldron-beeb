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
