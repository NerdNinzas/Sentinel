import { chromium } from "playwright-core";
const S = process.env.S;
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1100, height: 850 } });
await page.goto("http://localhost:9000/", { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await page.screenshot({ path: `${S}/payflow-ok.png` });
// hammer /pay from inside the page to drain the pool
await page.evaluate(async () => {
  for (let r = 0; r < 8; r++) await Promise.all(Array.from({ length: 50 }, () => fetch("/pay", { method: "POST" }).catch(() => {})));
});
await page.waitForTimeout(3500);
await page.screenshot({ path: `${S}/payflow-outage.png` });
await browser.close();
console.log("done");
