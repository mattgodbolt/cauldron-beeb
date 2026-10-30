# The original

*Cauldron* (Palace Software, 1985) for the 48K ZX Spectrum, as preserved
by [Spectrum Computing](https://spectrumcomputing.co.uk/entry/850/)
(ZXDB entry 850). Designed by Steve Brown; the Spectrum version is by
Ramjam (Tony Barber, Simon Dunstan), as its menu says. Nothing here but
this file and `SHA256SUMS` is committed: the tapes, maps, screens and
text are not ours to redistribute.

    make fetch      # tools/fetch_original.sh: download and check them
    make zx         # simulate loading the tape: build/cauldron.z80

| File | What it is |
|---|---|
| `Cauldron.tap` | The release the port is made from (Palace's) |
| `Cauldron.tzx` | The same release as a TZX: the screen and the game's blocks are identical to the TAP's; its BASIC loader differs (the TAP's waits for a key before starting) |
| `Cauldron(Silverbird).tzx` | Silverbird's budget re-release, with its own loader and a differently laid out tape |
| `Cauldron.png` | The whole map |
| `Cauldron_Part1-4.jpg` | Maps in parts |
| `Cauldron.scr`, `Cauldron.gif` | Loading screen, an in-game screenshot |
| `Cauldron.txt` | The inlay text (Silverbird's) |
| `Cauldron.pok` | POKEs: lives, magic, keys, ingredients — useful addresses |
| `Cauldron_inlay.jpg` | Palace's inlay |
