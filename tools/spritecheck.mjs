#!/usr/bin/env node
// Run tools/spritecases.py's cases on the BBC: each case's scene drawn by
// the viewer, its blocks and colours poked, its calls made through the
// viewer's sprite_test, and the screen and attributes dumped
// (build/sprite/bbc_NNN.bin) for `spritecases.py cmp`.
//
//   node tools/spritecheck.mjs [--disc build/viewer.ssd]
import { readFileSync, writeFileSync } from "fs";
import { startBeeb } from "./beeb.mjs";

const args = process.argv.slice(2);
const i = args.indexOf("--disc");
const disc = i >= 0 ? args[i + 1] : "build/viewer.ssd";
const cases = JSON.parse(readFileSync("build/sprite/cases.json", "utf8"));
const b = await startBeeb({ disc, bootUntil: "shown", symbols: disc.replace(/\.ssd$/, ".json") });
try {
    await b.write("view_sprites", [0]);     // the scenes alone
    await b.tap("SPACE");
    await b.runUntil("viewer_wait", 10);
    for (const [n, c] of cases.entries()) {
        await b.write("view_kind", [c.outdoors ? 0 : 1]);
        await b.write("view_num", [c.scene]);
        // Force a redraw even when the scene is the one shown.
        await b.write("view_shown", [0xff, 0xff]);
        await b.runUntil("viewer_wait", 10);
        await b.write("attr_p", [c.attr_p]);
        await b.write("attr_t", [c.attr_t]);
        await b.write("mask_t", [c.mask_t]);
        const blocks = [];
        for (const [gfx, x, y, rows, width, mode, attr] of c.blocks)
            blocks.push(gfx & 255, gfx >> 8, x, y, rows, width, mode, attr);
        await b.write("sprite_blocks", blocks);
        await b.write("test_calls", c.calls);
        await b.write("test_n", [c.calls.length]);
        const r = await b.runUntil("test_done", 10);
        if (r.stopped_reason !== "breakpoint") console.log("case", n, "never finished");
        const scr = await b.read(0x5000, 0x3000);
        const attrs = await b.read("attrs", 768);
        writeFileSync(`build/sprite/bbc_${String(n).padStart(3, "0")}.bin`, Buffer.from([...scr, ...attrs]));
    }
} finally {
    await b.close();
}
