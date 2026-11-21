// 补 emoji：node tools/fetch_emoji.mjs 1f4fa 2753
// 从 jsdelivr 拉 twemoji 72x72 PNG 到 assets/emoji/<codepoint>.png
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const DIR = path.join(HERE, "..", "assets", "emoji");
const MIRRORS = [
  "https://gcore.jsdelivr.net/gh/twitter/twemoji@v14.0.2/assets/72x72/",
  "https://testingcf.jsdelivr.net/gh/twitter/twemoji@v14.0.2/assets/72x72/",
  "https://cdn.jsdelivr.net/gh/twitter/twemoji@v14.0.2/assets/72x72/",
];

const cps = process.argv.slice(2).map((s) => s.trim().toLowerCase()).filter(Boolean);
if (!cps.length) {
  console.log("usage: node tools/fetch_emoji.mjs <codepoint> [codepoint...]");
  process.exit(1);
}
fs.mkdirSync(DIR, { recursive: true });

for (const cp of cps) {
  const out = path.join(DIR, `${cp}.png`);
  if (fs.existsSync(out)) {
    console.log(cp, "skip (exists)");
    continue;
  }
  let ok = false;
  for (const base of MIRRORS) {
    try {
      const r = await fetch(base + `${cp}.png`);
      if (!r.ok) continue;
      const buf = Buffer.from(await r.arrayBuffer());
      if (buf.length < 100) continue;
      fs.writeFileSync(out, buf);
      console.log(cp, "ok", buf.length, "bytes");
      ok = true;
      break;
    } catch (e) {
      console.log(cp, "fail", base, String(e).slice(0, 80));
    }
  }
  if (!ok) console.log(cp, "FAILED");
}
