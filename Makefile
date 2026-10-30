# CAULDRON — BBC Micro port
#
#   make          assemble build/cauldron.ssd (+ build/cauldron.json, the
#                 symbols, and build/listing.txt)
#   make run      boot it in jsbeeb, screenshot to shots/run.png
#   make check    every check: make draw (MODEL=Master to run them on a
#                 Master 128; default B-DFS1.2)
#   make passes   the original and the port played side by side with the
#                 same keys and seed (tests/scenarios.txt), their variables
#                 compared at every pass (tools/zxpass.py, tools/beepass.mjs,
#                 tools/passcmp.py)
#   make draw     every outdoor scene (panel, sky, landscape screen) and
#                 room the BBC draws, byte for byte against the original's
#                 own drawing of them (tools/drawcheck.mjs, tools/drawcmp.py,
#                 tools/zxscene.py), attributes too
#   make vm       every statement of the compiled BASIC the interpreter can
#                 run, against the original's Z80 from the same random state
#                 (tools/bas2vm.py, src/vm.6502, tools/vmcheck.py)
#   make sprites  SPRITE on random cases against the original's
#                 (tools/spritecases.py, tools/spritecheck.mjs)
#   make splits   the palette splits' timing, the panel's rows checked in a
#                 screenshot (tools/splitsweep.py, decision 4)
#   make disc     rebuild from a clean tree and copy the disc to
#                 cauldron.ssd, which the README links
#   make fetch    download the Spectrum original into original/
#   make zx       load the original's tape into build/cauldron.z80, stopped
#                 at the game's entry (24600, after the loader's PAUSE)
#   make disasm   the original's disassembly with the research's labels,
#                 build/cauldron.skool (from disasm/*.ctl)
#   make bas      the compiled BASIC decompiled to build/cauldron.bas
#                 (tools/decompile.py; execution maps in build/maps/*.txt)
#   make venv     the Python tools' environment (.venv with SkoolKit, Pillow)

PYTHON  ?= .venv/bin/python
BARON   ?= $(firstword $(wildcard ../baron/build/src/baron) baron)
# Baron, failing on a warning too (every disc builds with --warn 2).
ASM      = BARON=$(BARON) tools/asm.sh
# The jsbeeb model the test tools use (tools/beeb.mjs reads CAULDRON_MODEL).
MODEL   ?= B-DFS1.2
export CAULDRON_MODEL = $(MODEL)
TARGET   = build/cauldron.ssd
DISC     = cauldron.ssd
SOURCES  = $(wildcard src/*.6502)
# Made from the original by the tools, never committed (original/README.md).
GENERATED = build/data/title.bin build/data/landmap.bin build/logic.6502
VIEWER   = build/viewer.ssd
TEST     = build/test.ssd
# Stamped into !BOOT, so a disc says what it is: UTC build time and the
# commit, with + if the tree had changes.
BUILD   := $(shell date -u '+%Y-%m-%d %H:%M UTC') $(shell git rev-parse --short HEAD 2>/dev/null || echo NOGIT)$(shell git diff --quiet HEAD -- . ':(exclude)$(DISC)' ':(exclude)viewer.ssd' 2>/dev/null || echo +)

.DELETE_ON_ERROR:
.PHONY: all run check vm passes draw sprites splits disc fetch zx disasm venv clean

all: $(TARGET) $(VIEWER)

$(TARGET): $(SOURCES) $(GENERATED) | build
	@python3 tools/lint_labels.py > /dev/null || python3 tools/lint_labels.py
	$(ASM) -D 'BUILD="$(BUILD)"' -o $@ --title CAULDRON --opt 3 --warn 2 --symbols $(@:.ssd=.json) -v -log0 build/listing.txt src/main.6502

# The viewer: the same program with -D VIEWER=1, stepping through the
# scenes for the drawing's checks instead of playing.
$(VIEWER): $(SOURCES) $(GENERATED) | build
	$(ASM) -D VIEWER=1 -D 'BUILD="$(BUILD) viewer"' -o $@ --title CAULDRON --opt 3 --warn 2 --symbols $(@:.ssd=.json) src/main.6502

# The tests' disc: the game with -D VMBRK=1, the interpreter's
# breakpoints (vm_hit for a statement, vm_pass for a pass) built in.
$(TEST): $(SOURCES) $(GENERATED) | build
	$(ASM) -D VMBRK=1 -D 'BUILD="$(BUILD) test"' -o $@ --title CAULDRON --opt 3 --warn 2 --symbols $(@:.ssd=.json) src/main.6502

# The original's BASIC, compiled for the interpreter (decision 10).
# The statements a pass runs most (tools/zxhot.py) are compiled to native
# code: NATIVE of them.
NATIVE ?= 120
build/native.cfg: FORCE | build
	@echo '$(NATIVE)' | cmp -s - $@ || echo '$(NATIVE)' > $@
build/logic.6502: build/native.cfg build/cauldron.z80 build/hot.json tools/bas2vm.py tools/bas2native.py tools/decompile.py tools/decompile_names.py
	$(PYTHON) tools/bas2vm.py --hot build/hot.json --native $(NATIVE)

build/hot.json: build/cauldron.z80 tools/zxhot.py tests/scenarios.txt
	$(PYTHON) tools/zxhot.py

build/data/title.bin: original/Cauldron.scr tools/mkscreen.py
	python3 tools/mkscreen.py $< $@

check: vm passes draw sprites splits

# The original and the port played side by side (tests/scenarios.txt),
# their variables compared at every pass.
passes: $(TEST) build/cauldron.z80
	$(PYTHON) tools/zxpass.py
	node tools/beepass.mjs
	$(PYTHON) tools/passcmp.py

vm: build/cauldron.z80 build/logic.6502
	$(PYTHON) tools/vmcheck.py

# SPRITE against the original's on random cases (tools/spritecases.py:
# the attributes exactly, the pixels by decision 5's model of it).
sprites: $(VIEWER) build/sprite/seed1.json
	node tools/spritecheck.mjs
	$(PYTHON) tools/spritecases.py cmp

build/sprite/seed1.json: build/cauldron.z80 tools/spritecases.py
	$(PYTHON) tools/spritecases.py gen --count 100 --seed 1
	cp build/sprite/cases.json $@

# The palette splits where the build puts them (decision 4): the panel's
# rows in their colours, no pixel wrong.
splits: $(VIEWER)
	python3 tools/splitsweep.py $$(sed -n 's/^    SPLIT_ADJ = \([0-9]*\)$$/\1/p' src/irq.6502) 1000 1000 --check

draw: $(VIEWER) build/zxscenes/room_63.scr
	node tools/drawcheck.mjs
	$(PYTHON) tools/drawcmp.py

# The oracle: every scene drawn by the original's own code.
build/zxscenes/room_63.scr: build/cauldron.z80 tools/zxscene.py
	$(PYTHON) tools/zxscene.py

# Always from a clean tree, so the stamp names the commit the disc holds.
disc:
	@git diff --quiet HEAD -- . ':(exclude)$(DISC)' ':(exclude)viewer.ssd' || { echo "commit first: the stamp would say +"; exit 1; }
	rm -f $(TARGET) $(VIEWER)
	$(MAKE) $(TARGET) $(VIEWER)
	cp $(TARGET) $(DISC)
	cp $(VIEWER) viewer.ssd

# The original's tables and the colour maps (decision 3).
build/data/landmap.bin: build/cauldron.z80 tools/mkdata.py tools/colourstudy.py tools/zxgfx.py
	$(PYTHON) tools/mkdata.py

run: $(TARGET)
	node tools/play.mjs 'f5,!run' shots/ --disc $(TARGET) --until shown

build:
	mkdir -p build

fetch:
	tools/fetch_original.sh

zx: build/cauldron.z80

# The TAP's BASIC loads the screen and the game, returns, waits for a key
# (PAUSE 0) and then calls 24600: run it to there with a key held.
build/cauldron.z80: original/Cauldron.tap | build
	.venv/bin/tap2sna.py original/Cauldron.tap build/loaded.z80
	$(PYTHON) tools/zx.py '1,SPACE:down,@24600,SPACE:up,>cauldron' build/ --snap build/loaded.z80

disasm: build/cauldron.skool

build/cauldron.skool: build/cauldron.z80 $(wildcard disasm/*.ctl)
	rm -rf build/ctl && mkdir -p build/ctl
	for f in disasm/*.ctl; do grep -v '^i' $$f > build/ctl/$$(basename $$f); done
	.venv/bin/sna2skool.py -H -c build/ctl build/cauldron.z80 > $@

bas: build/cauldron.bas

# The listing marks statements no map in build/maps ran (tools/zx.py --map).
build/cauldron.bas: build/cauldron.z80 tools/decompile.py tools/decompile_names.py $(wildcard build/maps/*.txt)
	$(PYTHON) tools/decompile.py $(addprefix --map ,$(wildcard build/maps/*.txt))

original/Cauldron.tap:
	tools/fetch_original.sh

venv:
	uv venv .venv && uv pip install --python .venv/bin/python skoolkit pillow

clean:
	rm -rf build

FORCE:
