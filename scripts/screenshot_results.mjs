// Screenshot the results page (mock data) to verify the AdaptPanel renders.
import { chromium } from "playwright";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 1600 } });
await page.goto("http://localhost:3000/results", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const panel = page.locator('section[aria-label="Revised KV generation"]');
await panel.scrollIntoViewIfNeeded();
await page.screenshot({ path: "adapted-kv/ui-adapt-panel.png", fullPage: false });
console.log("panel visible:", await panel.isVisible());
console.log("button text:", await panel.locator("button").textContent());
await browser.close();
