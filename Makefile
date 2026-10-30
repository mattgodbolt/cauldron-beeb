# CAULDRON — BBC Micro port
#
#   make fetch    download the Spectrum original into original/
#   make zx       load the original's tape into build/cauldron.z80, stopped
#                 at the game's entry (24600, after the loader's PAUSE)
#   make disasm   the original's disassembly with the research's labels,
#                 build/cauldron.skool (from disasm/*.ctl)
#   make venv     the Python tools' environment (.venv with SkoolKit, Pillow)

PYTHON  ?= .venv/bin/python

.DELETE_ON_ERROR:
.PHONY: all fetch zx disasm venv clean

all: zx

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

original/Cauldron.tap:
	tools/fetch_original.sh

venv:
	uv venv .venv && uv pip install --python .venv/bin/python skoolkit pillow

clean:
	rm -rf build
