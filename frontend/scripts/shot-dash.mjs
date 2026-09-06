import { chromium } from "playwright-core";
const S = process.env.S;
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.goto("http://localhost:3000", { waitUntil: "domcontentloaded" });
await page.evaluate(() => localStorage.setItem("sentinel.session", "st_testsession123"));
await page.goto("http://localhost:3000/dashboard", { waitUntil: "networkidle" });
await page.waitForSelector("text=Welcome back", { timeout: 20000 });
await page.waitForTimeout(700);
await page.screenshot({ path: `${S}/dash-overview.png` });
for (const v of ["WAR ROOMS", "INTEGRATIONS", "PROFILE", "SETTINGS"]) {
  await page.click(`button:has-text("${v}")`);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${S}/dash-${v.toLowerCase().replace(" ", "")}.png` });
}
console.log("errors:", errors.length ? errors.join(" | ").slice(0, 300) : "none");
await browser.close();
