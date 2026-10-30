# CAULDRON (BBC Micro port) — notes for Claude Code

A port of Palace Software's *Cauldron* (ZX Spectrum 48K, 1985; designed by
Steve Brown, the Spectrum version by Ramjam) to the BBC Micro, in 6502
assembly built with [baron](https://github.com/waitingforvsync/baron) and
tested in a headless jsbeeb through its MCP server. The Spectrum original
runs headless too, on SkoolKit's Z80 simulator, so the two can be compared.
Run the way `../chuckie-egg-2-beeb` and `../nm` were, from
`../porting-to-the-beeb.md`; their tools and docs are the model.

Targets (Matt, 2026-10-30): a Model B with 16K of sideways RAM, and the
Master 128, from one disc.

- `docs/journal.md`: how it got here, in order. Add to it as you go.
- `docs/research.md` and `docs/research/*.md`: what the original is and
  how it works.
- `docs/decisions.md`: every call the port makes that the original didn't,
  numbered, with the reason. Nothing is changed from the original quietly.

## The rules (from kieranhj/beeb-port-kit)

1. **The original is the specification.** Find what the Spectrum code does
   and transcribe it: its tables, constants and logic, verbatim where the
   hardware allows. When the BBC forces a change, port the original's
   *decision*, not just its effect. The map stays identical.
2. **Deviations are numbered decisions** in `docs/decisions.md`. Matt
   makes the design calls: lay out the options with figures. A call made
   while Matt is away is marked provisional there, for review.
3. **One layer at a time**, working and visible in the emulator before the
   next one starts: screen, data, drawing, player, monsters, objects,
   sound, front end, loader.
4. **Measure, don't recall.** Run it, read the bytes, read memory back.
   Verify against the buffer, not the screenshot.

## House rules

- Commit messages end at `Co-Authored-By:`; never a claude.ai session link
  or a `Claude-Session:` trailer. The repo is pushed to GitHub
  (`origin`, public): never force-push; fix with additive commits.
- Comments and docs carry no figure the build computes or one run
  measured (addresses, sizes, free bytes). Name the symbol, `ASSERT` the
  property, or cite the dated decision. The original's addresses and the
  hardware's are fine.
- Never label a statement "honest" or "candid". Size work by what it
  touches, never by time. Matt is they/them.
- Every agent brief carries these rules.

## Commands

```sh
make fetch      # download the original into original/ (not committed)
make zx         # load the tape into build/cauldron.z80, at the game's entry
make disasm     # build/cauldron.skool from disasm/*.ctl
make bas        # build/cauldron.bas: the compiled BASIC, decompiled (tools/decompile.py)
make venv       # .venv with SkoolKit and Pillow (needs uv)
```

## Testing

- `.venv/bin/python tools/zx.py '<script>' shots/zx_`: the Spectrum
  (`--snap`, default `build/cauldron.z80`). Steps: a number waits seconds,
  `f10` frames, `X:tap`/`X:1.5`/`X:down`/`X:up`, `!name` screenshots,
  `>name` snapshots, `?addr:n` peeks, `=addr:v1/v2` pokes, `@addr` runs to
  an address. Spectrum key names (`CAPS`, `SYM`, `ENTER`, `SPACE`, A-Z,
  0-9) and `KL KR KU KD KF` for Kempston. `--map FILE` logs executed
  addresses; `--ports FILE` logs the beeper's writes.
- `node tools/play.mjs '<script>' shots/p_ [--disc build/X.ssd]`: the BBC,
  the same language (jsbeeb's key names), plus `#name` screen dumps and
  `@label` / `?sym` by baron symbol.
- `python3 tools/grid.py out.png cols a.png b.png ...` tiles screenshots.

## The original, briefly

- The TAP's BASIC loads the screen at 40000 (copied to the display), the
  game at 24600-65535, waits for a key and calls 24600. The menu: 1
  Kempston, 2 Sinclair II, 3 keys (CAPS SHIFT to V), 4 play.

## The BBC side

- `make` builds `build/cauldron.ssd` (`src/main.6502`) with its symbols in
  `build/cauldron.json`; `make run` boots it to the label `shown`.
- Data converted from the original is made into `build/data/` by the
  tools at build time (`tools/mkscreen.py`), never committed.
- `make check` before every commit, and read its exit status (never pipe
  it into `tail`). `make check MODEL=Master` runs it on a Master 128.
  `make draw` compares every scene the viewer draws, byte for byte,
  with the original's own code drawing it (tools/zxscene.py).
- Memory: CAULDRN loads at `&1900`; its loader puts CAULDAT (the
  original's data, `Data` in `src/main.6502`) in a sideways RAM bank,
  paged in for good, and TITLE in the screen, then copies the game down
  to `&0E00`. The workspace follows the code (`Work`, virtual). Pages
  4-12 hold the cells' scenery (decision 5, `draw.6502`).
- The screen's lit pixels and the attribute shadow `attrs` are exactly
  the original's at all times (the logic reads them: ATTR, POINT); only
  colours are the port's (decisions 4 and 5). Every drawing routine
  keeps that, and the checks prove it.
- `make check` also runs `make sprites` (SPRITE against the original's
  on random cases) and `make splits`.
- `!BOOT` mustn't load into screen memory: the OS echoes `!BOOT`'s lines
  into MODE 7's screen at `&7C00`, inside ours. The game loads with OSFILE
  before it takes the machine.
