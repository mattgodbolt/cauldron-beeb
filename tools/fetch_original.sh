#!/bin/sh
# Fetch the Spectrum original and its reference material from Spectrum
# Computing (ZXDB entry 850) into original/, and check them against
# original/SHA256SUMS. Not committed: they are not ours to redistribute.
set -e
cd "$(dirname "$0")/../original"
SC=https://spectrumcomputing.co.uk
get() { [ -f "$2" ] || curl -sfL "$1" -o "$2"; }
# getzip URL DEST: the zip's one tape, under the name given.
getzip() {
    [ -f "$2" ] && return
    curl -sfL "$1" -o fetch.zip
    member=$(unzip -Z1 fetch.zip | grep -iE '\.(tap|tzx)$' | head -1)
    unzip -p fetch.zip "$member" > "$2" && rm fetch.zip
}
getzip "$SC/pub/sinclair/games/c/Cauldron.tap.zip" Cauldron.tap
getzip "$SC/pub/sinclair/games/c/Cauldron.tzx.zip" Cauldron.tzx
getzip "$SC/pub/sinclair/games/c/Cauldron(SilverbirdSoftwareLtd).tzx.zip" "Cauldron(Silverbird).tzx"
get "$SC/pub/sinclair/games-info/c/Cauldron.txt" Cauldron.txt
get "$SC/pub/sinclair/games-maps/c/Cauldron.png" Cauldron.png
for p in 1 2 3 4; do
    get "$SC/pub/sinclair/games-maps/c/Cauldron_Part$p.jpg" "Cauldron_Part$p.jpg"
done
get "$SC/pub/sinclair/screens/load/c/scr/Cauldron.scr" Cauldron.scr
get "$SC/pub/sinclair/screens/in-game/c/Cauldron.gif" Cauldron.gif
get "$SC/zxdb/sinclair/pokes/c/Cauldron%20(1985)(Palace%20Software).pok" Cauldron.pok
get "$SC/zxdb/sinclair/entries/0000850/Cauldron.jpg" Cauldron_inlay.jpg
sha256sum -c --quiet SHA256SUMS
