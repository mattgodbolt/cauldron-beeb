#!/usr/bin/env node
// Frames (VSyncs) and cycles each main-loop pass takes on the test disc,
// with keys held: is decision 6's pace kept?
//
//   node tools/passtime.mjs [keys] [passes] [--model M]
//
// keys: jsbeeb key names joined with +, held from the first pass (e.g.
// COLON_STAR+X to fly up and right). Also each pass's work: the cycles
// from its start to op_pass (vm_pass_due), before the wait for the pace.
import { startBeeb } from "./beeb.mjs";

const args = process.argv.slice(2);
const mi = args.indexOf("--model");
const model = mi >= 0 ? args.splice(mi, 2)[1] : undefined;
const keys = (args[0] ?? "").split("+").filter(Boolean);
const n = parseInt(args[1] ?? "40");
const b = await startBeeb({ disc: "build/test.ssd", bootUntil: "shown", symbols: "build/test.json", model });
try {
    await b.keyDown("K4"); await b.keyDown("SPACE"); await b.run(1); await b.keyUp("SPACE");
    for (let i = 0; i < 3; i++) await b.runUntil("vm_pass", 60);
    await b.keyUp("K4");
    for (const k of keys) await b.keyDown(k);
    const frames = [], cycles = [], work = [];
    const now = async () => JSON.parse(await b.regs()).elapsed_cycles;
    let v0 = await b.peek("vsyncs"), c0 = await now();
    for (let i = 0; i < n; i++) {
        await b.runUntil("vm_pass_due", 60);
        work.push((await now()) - c0);
        await b.runUntil("vm_pass", 60);
        const v = await b.peek("vsyncs"), c = await now();
        frames.push((v - v0) & 255); cycles.push(c - c0);
        v0 = v; c0 = c;
    }
    const stats = (xs) => {
        const s = [...xs].sort((a, b) => a - b);
        return `min ${s[0]}, median ${s[s.length >> 1]}, max ${s[s.length - 1]}`;
    };
    console.log("frames a pass:", frames.join(" "));
    console.log(`work a pass: ${stats(work)}`);
    if (process.env.PASSTIME_ALL) console.log("work:", work.join(" "));
    console.log(`cycles a pass: ${stats(cycles)} (5 frames: 200000)`);
} finally {
    await b.close();
}
process.exit(0);
