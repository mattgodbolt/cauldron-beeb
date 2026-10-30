#!/usr/bin/env node
// The port's side of make passes: each scenario's variables at the top of
// every main-loop pass, on the test disc (build/test.ssd, -D VMBRK=1).
//
//   node tools/beepass.mjs [scenario ...]
//
// As tools/zxpass.py does on the original: RND's seed set just after
// RANDOMIZE (statement 25606), 4 held until the house (26691), then at
// each pass (op_pass's vm_pass) the variables (bv) noted and the pass's
// keys held. Writes build/passes/<name>.bbc.json.
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { startBeeb } from "./beeb.mjs";

const KEYS = { L: "Z", R: "X", U: "COLON_STAR", D: "SLASH", F: "RETURN" };
const VARS_LEN = 41575 - 41015;

function scenarios() {
    const out = {};
    for (let line of readFileSync("tests/scenarios.txt", "utf8").split("\n")) {
        line = line.split("#")[0].trim();
        if (!line) continue;
        const [name, seed, ...steps] = line.split(/\s+/);
        const passes = [];
        for (const st of steps) {
            const [keys, n = "1"] = st.split("*");
            for (let i = 0; i < parseInt(n); i++) passes.push(keys.replace("-", ""));
        }
        out[name] = { seed: parseInt(seed), passes };
    }
    return out;
}

const want = process.argv.slice(2);
mkdirSync("build/passes", { recursive: true });
for (const [name, { seed, passes }] of Object.entries(scenarios())) {
    if (want.length && !want.includes(name)) continue;
    const b = await startBeeb({ disc: "build/test.ssd", bootUntil: "shown", symbols: "build/test.json" });
    try {
        const stmt = async (addr) => {
            const l = b.syms[`L${addr}`];
            await b.write("vm_brk", [l & 255, l >> 8]);
            const r = await b.runUntil("vm_hit", 60);
            if (r.stopped_reason !== "breakpoint") throw new Error(`never reached statement ${addr}`);
            await b.write("vm_brk", [0, 0]);
        };
        // (SPACE starts the program at once: the breakpoint is armed first.)
        await b.keyDown("SPACE");
        await stmt(25606);
        await b.keyUp("SPACE");
        await b.write("rnd_seed", [seed & 255, seed >> 8]);
        await b.keyDown("K4");
        await stmt(26691);
        await b.keyUp("K4");
        const blocks = [];
        let held = [];
        for (const keys of [...passes, ""]) {
            const r = await b.runUntil("vm_pass", 60);
            if (r.stopped_reason !== "breakpoint") {
                const pc = JSON.parse(await b.regs()).pc;
                const stop = Object.entries(b.syms).find(([k, v]) => v === pc && /^vm_|print_bad/.test(k));
                const acc = await b.peekw("acc");
                console.log(`${name}: pass ${blocks.length} never began: ${stop ? stop[0] : "pc " + pc.toString(16)}, acc ${acc}`);
                break;
            }
            blocks.push(Buffer.from(await b.read("bv", VARS_LEN)).toString("hex"));
            for (const k of held) await b.keyUp(KEYS[k]);
            held = [...keys];
            for (const k of held) await b.keyDown(KEYS[k]);
        }
        writeFileSync(`build/passes/${name}.bbc.json`, JSON.stringify(blocks));
        console.log(`${name}: ${blocks.length} passes`);
    } finally {
        await b.close();
    }
}
process.exit(0);
