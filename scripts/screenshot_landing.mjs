// Screenshot the landing page to verify the ImageStreamHero corridor renders.
import { chromium } from "playwright";

const base = process.env.BASE_URL || "http://localhost:3111";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(base, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await page.screenshot({ path: "adapted-kv/ui-landing-hero-1.png" });
await page.waitForTimeout(4000);
await page.screenshot({ path: "adapted-kv/ui-landing-hero-2.png" });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
console.log("h1:", await page.locator("h1").first().textContent());
console.log("corridor cards:", await page.locator('[aria-label="Hero"] img').count());
console.log("page errors:", errors.length ? errors : "none");
await browser.close();
