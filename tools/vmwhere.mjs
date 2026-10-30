#!/usr/bin/env node
// Run the game disc and say where the interpreter is: the statement (the
// original's address, by the nearest label at or before vpc), whether
// it's stopped at vm_unbuilt (and what for), and a screenshot.
//
//   node tools/vmwhere.mjs [script] [--disc build/cauldron.ssd] [--model M]
//
// The script is tools/play.mjs's, run after the title's key.
import { startBeeb } from "./beeb.mjs";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const disc = opt("disc", "build/cauldron.ssd");
const model = opt("model", undefined);
const script = args[0] ?? "3";
const b = await startBeeb({ disc, bootUntil: "shown", symbols: disc.replace(/\.ssd$/, ".json"), model });
try {
    await b.tap("SPACE");
    for (const raw of script.split(",")) {
        const step = raw.trim();
        if (!step) continue;
        if (step.startsWith("!")) console.log("SHOT", await b.shot(`shots/w_${step.slice(1)}.png`));
        else if (/^f\d+$/.test(step)) await b.frames(parseInt(step.slice(1)));
        else if (/^[\d.]+$/.test(step)) await b.run(parseFloat(step));
        else {
            const [key, action = "tap"] = step.split(":");
            if (action === "down") await b.keyDown(key);
            else if (action === "up") await b.keyUp(key);
            else await b.tap(key, action === "tap" ? 0.1 : parseFloat(action));
        }
    }
    const regs = JSON.parse(await b.regs());
    const vpc = await b.peekw("vpc");
    const labels = Object.entries(b.syms).filter(([k]) => /^L\d+$/.test(k)).sort((x, y) => x[1] - y[1]);
    let at = null;
    for (const [k, v] of labels) if (v <= vpc) at = k;
    const stops = ["vm_unbuilt", "vm_bad_address", "vm_bad_kind", "print_bad"];
    const stop = stops.find((s) => b.syms[s] === regs.pc);
    const acc = await b.peekw("acc");
    console.log(`pc ${regs.pc.toString(16)}${stop ? " (" + stop + ")" : ""}, vpc ${vpc.toString(16)} in ${at}, acc ${acc}`);
    console.log("SHOT", await b.shot("shots/w_end.png"));
} finally {
    await b.close();
}
process.exit(0);
