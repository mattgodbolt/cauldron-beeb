#!/usr/bin/env node
// A sampling profiler for the game on the test disc: the PC sampled every
// 397 cycles in play (keys held as tools/passtime.mjs takes them) and
// charged to the nearest label in main RAM. Labels in the bytecode's bank
// (L<n>) don't count: the interpreter's own code is where the time goes.
//
//   node tools/sample.mjs [keys] [samples]
import { startBeeb } from "./beeb.mjs";

const keys = (process.argv[2] ?? "").split("+").filter(Boolean);
const n = parseInt(process.argv[3] ?? "3000");
const b = await startBeeb({ disc: "build/test.ssd", bootUntil: "shown", symbols: "build/test.json" });
await b.keyDown("K4"); await b.keyDown("SPACE"); await b.run(1); await b.keyUp("SPACE");
for (let i = 0; i < 3; i++) await b.runUntil("vm_pass", 60);
await b.keyUp("K4");
for (const k of keys) await b.keyDown(k);
for (let i = 0; i < 3; i++) await b.runUntil("vm_pass", 60);
const syms = Object.entries(b.syms).filter(([k, v]) => typeof v === "number" && !k.includes(".") && v >= 0x0e00 && v < 0x8000
    && /^[a-z]/.test(k)).sort((a, b) => a[1] - b[1]);
const routine = (a) => {
    if (a >= 0xc000) return "OS";
    let lo = 0, hi = syms.length - 1, best = "?";
    while (lo <= hi) { const m = (lo + hi) >> 1; if (syms[m][1] <= a) { best = syms[m][0]; lo = m + 1; } else hi = m - 1; }
    return best;
};
const hist = {};
for (let i = 0; i < n; i++) {
    await b.cycles(397);
    const pc = JSON.parse(await b.regs()).pc;
    const name = routine(pc);
    hist[name] = (hist[name] ?? 0) + 1;
}
const total = Object.values(hist).reduce((a, c) => a + c, 0);
for (const [k, v] of Object.entries(hist).sort((a, c) => c[1] - a[1]).slice(0, 30))
    console.log(`${(100 * v / total).toFixed(1).padStart(5)}%  ${k}`);
await b.close();
process.exit(0);
