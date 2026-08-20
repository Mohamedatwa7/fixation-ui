#!/usr/bin/env node
// Adapt a Key Visual using the Higgsfield CLI, driven by a fixation analysis result.
//
// Takes the recommendation JSON produced by the scoring backend (verdict.risks[].suggested_fix),
// builds an image-edit prompt from the ranked fixes, and runs an image-to-image edit on the
// original KV via `higgsfield generate create <model> --image <kv>`.
//
// Prerequisites:
//   npm i -g @higgsfield/cli
//   higgsfield auth login
//
// Usage:
//   node scripts/adapt-kv.mjs --result <analysis.json> --image <kv.png> [options]
//
// Options:
//   --result <path>        Analysis result JSON (required)
//   --image <path>         Original KV image to adapt (required)
//   --model <name>         Higgsfield model (default: nano_banana_2)
//   --risks <ranks>        Comma-separated risk ranks to apply, e.g. "1,2" (default: all)
//   --extra <text>         Extra edit instruction appended to the prompt
//   --aspect-ratio <r>     auto | 1:1 | 4:5 | 16:9 | ... (default: auto = closest to input image)
//   --resolution <r>       1k | 2k | 4k (default: 2k)
//   --out <dir>            Output directory (default: ./adapted-kv)
//   --dry-run              Print the prompt and command without calling Higgsfield

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

function fail(msg) {
  console.error(`error: ${msg}`);
  process.exit(1);
}

function parseArgs(argv) {
  const args = { model: "nano_banana_2", aspectRatio: "auto", resolution: "2k", out: "adapted-kv" };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) fail(`missing value for ${a}`);
      return argv[++i];
    };
    switch (a) {
      case "--result": args.result = next(); break;
      case "--image": args.image = next(); break;
      case "--model": args.model = next(); break;
      case "--risks": args.risks = next().split(",").map((s) => parseInt(s.trim(), 10)); break;
      case "--extra": args.extra = next(); break;
      case "--aspect-ratio": args.aspectRatio = next(); break;
      case "--resolution": args.resolution = next(); break;
      case "--out": args.out = next(); break;
      case "--dry-run": args.dryRun = true; break;
      case "--help": case "-h":
        console.log(fs.readFileSync(new URL(import.meta.url), "utf8").split("\n").filter((l) => l.startsWith("//")).map((l) => l.slice(3)).join("\n"));
        process.exit(0);
      default: fail(`unknown option: ${a}`);
    }
  }
  if (!args.result) fail("--result <analysis.json> is required");
  if (!args.image) fail("--image <kv image> is required");
  return args;
}

// The backend returns the verdict either at the top level or nested under result/data.
function findVerdictRoot(json) {
  for (const candidate of [json, json.result, json.data, json.analysis]) {
    if (candidate && typeof candidate === "object" && candidate.verdict) return candidate;
  }
  fail("no 'verdict' object found in result JSON — is this a fixation analysis result?");
}

function oneLine(text) {
  return String(text).replace(/\s+/g, " ").trim();
}

function buildPrompt(root, selectedRanks, extra) {
  const verdict = root.verdict;
  const risks = (verdict.risks || []).filter(
    (r) => !selectedRanks || selectedRanks.includes(r.rank)
  );
  if (risks.length === 0) fail("no matching risks in verdict (check --risks ranks)");

  const parts = [];
  parts.push(
    "Edit this advertising key visual. Apply the following revisions precisely while keeping the product, brand elements, overall layout and style otherwise unchanged."
  );
  risks.forEach((r, i) => {
    const fix = oneLine(r.suggested_fix || "");
    if (!fix) return;
    parts.push(`Revision ${i + 1}: ${fix}`);
  });
  if (extra) parts.push(`Also: ${oneLine(extra).replace(/([^.!?])$/, "$1.")}`);

  const strengths = (verdict.strengths || []).slice(0, 4).map(oneLine);
  if (strengths.length > 0) {
    parts.push(
      `Do not degrade what already works: ${strengths.join("; ")}.`
    );
  }
  parts.push("Photorealistic, production-quality advertising finish. Keep all existing text legible and unaltered unless a revision says otherwise.");
  return { prompt: parts.join(" "), appliedRisks: risks };
}

// Minimal PNG/JPEG dimension readers so --aspect-ratio auto can match the source KV.
function imageDimensions(file) {
  const buf = fs.readFileSync(file);
  if (buf.length > 24 && buf.readUInt32BE(0) === 0x89504e47) {
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
  }
  if (buf.length > 4 && buf.readUInt16BE(0) === 0xffd8) {
    let off = 2;
    while (off + 9 < buf.length) {
      if (buf[off] !== 0xff) break;
      const marker = buf[off + 1];
      const size = buf.readUInt16BE(off + 2);
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { height: buf.readUInt16BE(off + 5), width: buf.readUInt16BE(off + 7) };
      }
      off += 2 + size;
    }
  }
  return null;
}

const SUPPORTED_RATIOS = ["1:1", "3:2", "2:3", "4:3", "3:4", "4:5", "5:4", "9:16", "16:9", "21:9"];

function closestAspectRatio(width, height) {
  const target = width / height;
  let best = SUPPORTED_RATIOS[0];
  let bestDiff = Infinity;
  for (const r of SUPPORTED_RATIOS) {
    const [w, h] = r.split(":").map(Number);
    const diff = Math.abs(w / h - target);
    if (diff < bestDiff) { bestDiff = diff; best = r; }
  }
  return best;
}

function higgsfieldBin() {
  // Prefer the repo-local install (devDependency), fall back to a global install.
  const ext = process.platform === "win32" ? ".cmd" : "";
  const local = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "node_modules", ".bin", `higgsfield${ext}`);
  return fs.existsSync(local) ? local : `higgsfield${ext}`;
}

function runHiggsfield(cliArgs) {
  const bin = higgsfieldBin();
  if (process.platform === "win32") {
    // .cmd shims require a shell on modern Node; quote each arg for cmd.exe.
    const quoted = cliArgs.map((a) => `"${a.replace(/"/g, '\\"')}"`).join(" ");
    return spawnSync(`"${bin}" ${quoted}`, { shell: true, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
  }
  return spawnSync(bin, cliArgs, { encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}

// Prefer explicit result URLs (result_url, results[].url) and skip inputs/previews.
function collectUrls(value, urls = [], key = "") {
  if (typeof value === "string") {
    if (/^https?:\/\//.test(value) && /result/i.test(key) && !/min_/i.test(key)) urls.push(value);
  } else if (Array.isArray(value)) {
    value.forEach((v) => collectUrls(v, urls, key));
  } else if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) {
      if (/input/i.test(k)) continue;
      collectUrls(v, urls, k);
    }
  }
  return urls;
}

async function download(url, dest) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`download failed (${res.status}): ${url}`);
  fs.writeFileSync(dest, Buffer.from(await res.arrayBuffer()));
}

const args = parseArgs(process.argv.slice(2));

const resultPath = path.resolve(args.result);
const imagePath = path.resolve(args.image);
if (!fs.existsSync(resultPath)) fail(`result file not found: ${resultPath}`);
if (!fs.existsSync(imagePath)) fail(`image file not found: ${imagePath}`);

const root = findVerdictRoot(JSON.parse(fs.readFileSync(resultPath, "utf8")));
const { prompt, appliedRisks } = buildPrompt(root, args.risks, args.extra);

let aspectRatio = args.aspectRatio;
if (aspectRatio === "auto") {
  const dims = imageDimensions(imagePath);
  aspectRatio = dims ? closestAspectRatio(dims.width, dims.height) : "1:1";
  if (!dims) console.warn("warn: could not read image dimensions; defaulting aspect ratio to 1:1");
}

const cliArgs = [
  "generate", "create", args.model,
  "--prompt", prompt,
  "--image", imagePath,
  "--aspect_ratio", aspectRatio,
  "--resolution", args.resolution,
  "--wait", "--json",
];

console.log(`Applying ${appliedRisks.length} recommendation(s) from ${path.basename(resultPath)}:`);
appliedRisks.forEach((r) => console.log(`  [rank ${r.rank}, ${r.confidence}] ${oneLine(r.issue)}`));
console.log(`\nEdit prompt:\n${prompt}\n`);

if (args.dryRun) {
  console.log(`Command:\n  higgsfield ${cliArgs.map((a) => (/\s/.test(a) ? JSON.stringify(a) : a)).join(" ")}`);
  process.exit(0);
}

console.log(`Running Higgsfield ${args.model} (${aspectRatio}, ${args.resolution})...`);
const proc = runHiggsfield(cliArgs);
if (proc.error) {
  fail(`could not run 'higgsfield' — is it installed? (npm i -g @higgsfield/cli)\n${proc.error.message}`);
}
if (proc.status !== 0) {
  fail(`higgsfield exited with code ${proc.status}:\n${proc.stderr || proc.stdout}`);
}

// --json output: scan the job payload for result URLs rather than assuming a schema.
let job;
try {
  // Output may be an object or an array of jobs; parse from whichever bracket comes first.
  const starts = [proc.stdout.indexOf("{"), proc.stdout.indexOf("[")].filter((i) => i >= 0);
  job = JSON.parse(proc.stdout.slice(Math.min(...starts)));
} catch {
  fail(`could not parse higgsfield JSON output:\n${proc.stdout}`);
}

const urls = [...new Set(collectUrls(job))];
if (urls.length === 0) fail(`job completed but no result URLs found in output:\n${JSON.stringify(job, null, 2)}`);

const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
const outDir = path.resolve(args.out, `${stamp}-${args.model}`);
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "prompt.txt"), prompt);
fs.writeFileSync(path.join(outDir, "job.json"), JSON.stringify(job, null, 2));

let saved = 0;
for (const url of urls) {
  const ext = (new URL(url).pathname.match(/\.(png|jpe?g|webp|mp4)$/i) || [, "png"])[1];
  const dest = path.join(outDir, `kv-adapted-${++saved}.${ext}`);
  try {
    await download(url, dest);
    console.log(`saved: ${dest}`);
  } catch (e) {
    console.warn(`warn: ${e.message}`);
    saved--;
  }
}

if (saved === 0) fail("no result files could be downloaded (see URLs in job.json)");
console.log(`\nDone — ${saved} adapted KV(s) in ${outDir}`);
