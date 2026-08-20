// End-to-end test of the /api/adapt route against the local dev server.
import fs from "node:fs";

const base = process.argv[2] || "http://localhost:3000";
const img = fs.readFileSync("eval/calibration/data/media/3d003ee3-6fe9-4446-b5c1-a81abddeffe7.jpg");
const result = JSON.parse(fs.readFileSync(
  "adapted-kv/2026-08-20T11-05-04-nano_banana_2/rescore-v2.json", "utf8"));

const res = await fetch(`${base}/api/adapt`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    image: `data:image/jpeg;base64,${img.toString("base64")}`,
    risks: result.verdict.risks,
    strengths: result.verdict.strengths,
  }),
});
const submitted = await res.json();
console.log("submit:", res.status, JSON.stringify({ ...submitted, prompt: (submitted.prompt || "").slice(0, 120) + "..." }));
if (!res.ok) process.exit(1);

for (let i = 0; i < 100; i++) {
  await new Promise((r) => setTimeout(r, 3000));
  const s = await fetch(`${base}/api/adapt?request_id=${submitted.request_id}`);
  const status = await s.json();
  if (status.status !== "queued" && status.status !== "in_progress") {
    console.log("final:", JSON.stringify(status));
    if (status.status === "completed" && status.images[0]) {
      const dl = await fetch(`${base}/api/adapt?download=${encodeURIComponent(status.images[0])}`);
      const buf = Buffer.from(await dl.arrayBuffer());
      fs.writeFileSync("adapted-kv/route-test-revised.png", buf);
      console.log(`download proxy: ${dl.status}, ${buf.length} bytes -> adapted-kv/route-test-revised.png`);
    }
    process.exit(status.status === "completed" ? 0 : 1);
  }
  if (i % 5 === 0) console.log("poll:", status.status);
}
console.log("timed out");
process.exit(1);
