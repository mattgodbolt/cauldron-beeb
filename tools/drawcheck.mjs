#!/usr/bin/env node
// Draw every landscape screen and room in the BBC viewer and dump what it
// drew, for tools/drawcmp.py to compare with the original's.
//
//   node tools/drawcheck.mjs [--disc build/cauldron.ssd]
//
// Writes build/bbcdraw/land_NN.bin and room_NN.bin: the 12K screen, then
// the four physical colours of logical 0-3 (palette_phys).
import { mkdirSync, writeFileSync } from "fs";
import { startBeeb } from "./beeb.mjs";

const args = process.argv.slice(2);
const i = args.indexOf("--disc");
const disc = i >= 0 ? args[i + 1] : "build/cauldron.ssd";
mkdirSync("build/bbcdraw", { recursive: true });
const b = await startBeeb({ disc, bootUntil: "shown", symbols: disc.replace(/\.ssd$/, ".json") });
try {
    await b.tap("SPACE");
    await b.runUntil("viewer_wait", 10);
    let bad = 0;
    for (const [kind, name, count] of [[0, "land", 61], [1, "room", 64]]) {
        for (let n = 0; n < count; n++) {
            await b.write("view_kind", [kind]);
            await b.write("view_num", [n]);
            // Run until the viewer is back in its wait loop with this drawn.
            await b.runUntil("viewer_wait", 10);
            const shown = await b.read("view_shown", 2);
            if (shown[0] !== kind || shown[1] !== n) {
                console.log(name, n, "never shown");
                bad++;
            }
            const scr = await b.read(0x5000, 0x3000);
            const pal = await b.read("palette_phys", 4);
            writeFileSync(`build/bbcdraw/${name}_${String(n).padStart(2, "0")}.bin`, Buffer.from([...scr, ...pal]));
        }
    }
    if (bad) process.exitCode = 1;
} finally {
    await b.close();
}
