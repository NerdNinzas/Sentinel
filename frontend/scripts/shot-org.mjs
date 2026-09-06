import { chromium } from "playwright-core";
const S = process.env.S;
const browser = await chromium.launch({ channel: "chrome", headless: true });
const errors = [];
const mk = async () => { const p = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  p.on("pageerror", (e) => errors.push(e.message)); p.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); }); return p; };

const page = await mk();
const email = `owner${Date.now()}@nerdninzas.dev`;
await page.goto("http://localhost:3000/login", { waitUntil: "networkidle" });
await page.click('button:has-text("SIGN UP")');
await page.fill('input[placeholder="Vijay Singh"]', "Aatif Khan");
await page.fill('input[placeholder="you@company.com"]', email);
await page.fill('input[placeholder="8+ characters"]', "password123");
await page.click('button:has-text("CREATE ACCOUNT")');
await page.waitForSelector("text=How will you use it?", { timeout: 20000 });
await page.screenshot({ path: `${S}/org-onboarding.png` });
await page.click("text=Organization workspace");
await page.click('button:has-text("CONTINUE")');
await page.fill('input[placeholder="NerdNinzas"]', "NerdNinzas Labs");
await page.fill('input[placeholder="New Delhi, IN"]', "New Delhi, India");
await page.click('button:has-text("CREATE WORKSPACE")');
await page.waitForSelector("text=OVERVIEW", { timeout: 20000 });
await page.waitForTimeout(700);
await page.screenshot({ path: `${S}/org-tour.png` });
for (let i = 0; i < 5; i++) { await page.click('button:has-text("NEXT"), button:has-text("DONE")').catch(() => {}); await page.waitForTimeout(350); }
await page.click('button:has-text("TEAM")');
await page.waitForSelector("text=INVITE TEAMMATES", { timeout: 10000 });
await page.click('button:has-text("GENERATE INVITE LINK")');
await page.waitForSelector('input[value*="/invite/"]', { timeout: 10000 });
const link = await page.inputValue('input[value*="/invite/"]');
await page.screenshot({ path: `${S}/org-team.png` });
console.log("invite link:", link);

// second user accepts
const p2 = await mk();
await p2.goto(link, { waitUntil: "networkidle" });
await p2.waitForSelector("text=ACCEPT INVITATION", { timeout: 15000 });
await p2.screenshot({ path: `${S}/org-invite.png` });
await p2.click('button:has-text("ACCEPT INVITATION")');
await p2.waitForURL(/\/login/, { timeout: 15000 });
await p2.click('button:has-text("SIGN UP")');
await p2.fill('input[placeholder="Vijay Singh"]', "Rahul Sharma");
await p2.fill('input[placeholder="you@company.com"]', `member${Date.now()}@example.com`);
await p2.fill('input[placeholder="8+ characters"]', "password123");
await p2.click('button:has-text("CREATE ACCOUNT")');
await p2.waitForSelector("text=YOU HAVE BEEN ADDED", { timeout: 25000 });
await p2.screenshot({ path: `${S}/org-joined.png` });

// owner refreshes team
await page.reload({ waitUntil: "networkidle" });
await page.click('button:has-text("TEAM")');
await page.waitForSelector("text=Rahul Sharma", { timeout: 15000 });
await page.screenshot({ path: `${S}/org-team-2members.png` });
console.log("errors:", errors.length ? errors.join(" | ").slice(0, 400) : "none");
await browser.close();
