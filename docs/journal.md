# Journal

How the port got here, in order.

## 2026-10-30

### Starting

Matt set out to port *Cauldron* (Palace Software, 1985) from the 48K
Spectrum to the BBC Micro, run the way *Chuckie Egg 2* and *Ninja
Massacre* were (`../porting-to-the-beeb.md`). The targets are a Model B
with 16K of sideways RAM and the Master 128, from one disc, as for CE2
and nm.

ZXDB entry 850 has Palace's release as TAP and TZX, Silverbird's
re-release, a full map, maps in parts and POKEs; `make fetch` gets them
(`original/README.md`). The TAP and the TZX hold the same screen and game
blocks. ZXDB says the game was "authored with" Phipps Associates' BASIC
compiler, so some of the code may be compiled BASIC.

The harness came from the siblings: `tools/zx.py` (nm's, with its R
register patch taken out until Cauldron's own random reads are known),
`tools/beeb.mjs` and `tools/play.mjs` (CE2's), `asm.sh`, `grid.py`,
`lint_labels.py` and `zx02.py`.

The TAP's BASIC loads the loading screen to 40000 and copies it to the
display, loads the game to 24600-65535 headerless, returns, waits for a
key (`PAUSE 0`) and calls 24600. `make zx` simulates the load and runs to
24600 with a key held, giving `build/cauldron.z80`.
