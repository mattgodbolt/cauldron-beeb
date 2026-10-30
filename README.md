# Cauldron for the BBC Micro

A work-in-progress port of *Cauldron* (Palace Software, 1985), from the
48K ZX Spectrum to the BBC Micro: a Model B with 16K of sideways RAM, and
the Master 128, from one disc.

**[Run it in jsbeeb](https://bbc.xania.org/?autoboot&disc1=github:mattgodbolt/cauldron-beeb/cauldron.ssd)**
([on a Master](https://bbc.xania.org/?autoboot&model=Master&disc1=github:mattgodbolt/cauldron-beeb/cauldron.ssd))

It is early days. The disc shows only the first step of the screen
layer: the Spectrum's loading screen in the Spectrum's 256 x 192
geometry, in MODE 1's four colours. There is no game on it yet.

This is an unofficial port. *Cauldron* was designed by Steve Brown; the
Spectrum version, which this port is made from, is by Ramjam (Tony
Barber and Simon Dunstan). The original's files are not in this
repository: `make fetch` downloads them from
[Spectrum Computing](https://spectrumcomputing.co.uk/entry/850/).

## How it's made

The port is made the way the
[Chuckie Egg 2](https://github.com/mattgodbolt/chuckie-egg-2-beeb) and
Ninja Massacre ports were, after Kieran Connell's
[beeb-port-kit](https://github.com/kieranhj/beeb-port-kit): the original
is the specification, every deviation is a numbered decision in
`docs/decisions.md`, and the port is built one layer at a time, each
checked against the original running headless.

The Spectrum original turns out to be compiled BASIC, apart from a
runtime library and a few machine code helpers. So the specification of
its game logic is a BASIC program, recovered by a decompiler for its
compiler's output (`tools/decompile.py`, `docs/research/compiler.md`).

## Building

You need [baron](https://github.com/waitingforvsync/baron) (at
`../baron/build/src/baron` or on the PATH), Node, and
[uv](https://github.com/astral-sh/uv) for the Python tools.

```sh
npm ci          # the jsbeeb harness (jsbeeb-mcp)
make venv       # .venv with SkoolKit and Pillow
make fetch      # the original, from Spectrum Computing
make            # build/cauldron.ssd
make run        # boot it in jsbeeb, screenshot to shots/run.png
make zx         # the original, loaded, as build/cauldron.z80
```

## Layout

| Path | What |
|---|---|
| `src/` | the port, in 6502 assembly for baron |
| `tools/` | the build's converters, the harness for jsbeeb (`beeb.mjs`, `play.mjs`) and for the Spectrum (`zx.py`, on SkoolKit) |
| `docs/journal.md` | how it got here, in order |
| `docs/research/` | how the original works |
| `docs/decisions.md` | every call the port makes that the original didn't |
| `original/` | the original's checksums; `make fetch` puts the files here |

## Thanks

Kieran Connell for the port kit and jsbeeb-mcp, Rich Talbot-Watkins for
baron, Richard Dymond for SkoolKit, and Spectrum Computing (ZXDB) for
the original and its maps.
