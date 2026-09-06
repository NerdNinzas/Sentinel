# SENTINEL — WAR ROOM SCRIPT (word-for-word)

**Cast**
- **VIJAY SINGH** — Incident Commander (coordinates; gives the rollback approval)
- **PRABAL VERMA** — Backend Engineer (author of the change that broke it; proposes the fix)
- **ANKITA** — SRE / Monitoring (raises the alarm; creates the conflict; confirms recovery)
- **SENTINEL** — the AI (speaks in Kabir's voice; also posts to Slack)

**Three screens on the projector:** War Room (dark dashboard) · PayFlow status page
(`https://demo-payment-service.onrender.com/`) · Slack `#all-sentinel`.

Brief actions are in [brackets]. Everything else is spoken exactly as written. Target: ~5 minutes.

---

**[0:00 — Vijay clicks Declare SEV-1, then Invite Sentinel. Everyone clicks Join Voice.]**

**VIJAY:** Okay everyone, payments are failing in production. Support's getting complaints and our status page is red. I'm declaring this a SEV-1 and pulling in Sentinel.

**SENTINEL:** Sentinel here. I've joined the room and linked the payment-service repo. I'm tracking facts, hypotheses, actions and conflicts — and I'll only speak when it helps.

**VIJAY:** Good. Ankita, you're on monitoring — what are you seeing?

---

**[0:35 — Ankita, urgent]**

**ANKITA:** It's bad. Payment success rate has collapsed — we're down around twenty percent. And the database connection pool is completely pinned, it's sitting at a hundred percent utilization. This is not a blip.

**SENTINEL:** Confirmed from monitoring — payment success rate is critically low and DB connection utilization is at a hundred percent. I've recorded customer impact and flagged connection-pool exhaustion as the leading hypothesis.

**VIJAY:** How bad on the customer side?

**ANKITA:** Checkout is failing for most users right now. The support queue is climbing fast.

---

**[1:20 — Prabal, a little defensive]**

**PRABAL:** Hmm, but the application side looks fine to me. My queries are returning, the service isn't actually down.

**SENTINEL:** I want to flag conflicting information about database health. Ankita reports the connection pool is at a hundred percent, but Prabal says the application side looks fine. Can someone verify the current state before we treat this as settled?

**ANKITA:** I'm looking right at it — connections are maxed and payments are timing out waiting for the pool. The app looks up because it's *accepting* requests, but they're failing downstream.

**SENTINEL:** Understood — monitoring supports Ankita. The pool-exhaustion hypothesis is now confirmed by telemetry.

---

**[2:05 — Vijay]**

**VIJAY:** Okay, pool exhaustion is real. What changed? Did something ship recently?

**SENTINEL:** One recent change correlates. On the payment-service repo, commit eight-three-seven-c by Prabal-verma — "retry gateway timeouts" — was pushed shortly before this started. I've flagged it as suspect.

**PRABAL:** …that's mine. I pushed the retry-logic change last night to fix the checkout timeouts. I completed it and merged it.

**SENTINEL:** Verified — I can see Prabal-verma's commit eight-three-seven-c on the repo, and Jira ticket KAN-eleven, the retry-logic task, is marked Done. Your change checks out, Prabal. And that same retry change is exactly what correlates with the leak — each retry grabs a new database connection and never releases it on timeout, so the pool drains under load.

**PRABAL:** Yeah… that would do it.

---

**[2:55 — Prabal]**

**PRABAL:** Let's revert it. Roll it back to the previous version.

**SENTINEL:** Reverting a production deployment is an action I won't take on my own. I've prepared a revert of commit eight-three-seven-c and queued it for approval. Vijay, as incident commander, please approve or reject it on the dashboard.

**[The red HUMAN APPROVAL REQUIRED modal appears.]**

**VIJAY:** This is exactly the point — the AI proposes, a human decides. I'm approving the revert. [clicks **Approve as Vijay**]

**SENTINEL:** Vijay approved the revert. Opening and merging the pull request now, and watching for recovery.

---

**[3:25 — the redeploy is running; fill the wait]**

**VIJAY:** While that redeploys — look at what just happened. Sentinel opened a *real* pull request on GitHub and merged it. [switch to the GitHub tab briefly]

**ANKITA:** And it posted the whole thing to Slack, so the folks who aren't on this call are already in the loop. [switch to Slack #all-sentinel]

**VIJAY:** And everything on this board is evidence-backed. Look at the confidence matrix — high confidence on customer impact and pool exhaustion, but root-cause confidence only climbed *after* we confirmed the causal change. It never pretended to know more than it did.

**PRABAL:** That's the part I like — it didn't guess. It verified.

---

**[4:15 — the status page flips; switch to the PayFlow tab]**

**ANKITA:** It's recovering — success rate is climbing back, the pool is draining, payments are going through again.

**VIJAY:** And see the deploy version change up top — that's the real service redeploying, not a mock.

**SENTINEL:** Payment success has recovered and the connection pool is back to normal. The incident appears resolved. Root cause: the v4.2 retry change leaked database connections under load; it was reverted through an approved pull request. I've filed the follow-up tasks.

---

**[4:45 — Vijay clicks Report]**

**VIJAY:** That's Sentinel. It listened, separated what we *knew* from what we *guessed*, caught the conflict, verified Prabal's change against GitHub and Jira, and never touched production without me. And it's already written the postmortem — impact, findings, the decision ledger with my approval, and the open risks.

**VIJAY:** One AI teammate — in the room, on voice, Slack, GitHub and Jira — turning a chaotic outage into a shared, evidence-backed source of truth. Thank you.

**[END — 5:00]**

---

## OPTIONAL LINES (drop in if you have time)

**Hinglish (put in Beat 2 or 4 — shows the multilingual voice):**

**VIJAY:** Sentinel, abhi status kya hai?

**SENTINEL:** Vijay, payment success rate abhi bahut low hai aur database pool sau percent par hai — hum pool exhaustion investigate kar rahe hain.

**Catch-a-bluff (Beat 4 — shows verification's teeth):**

**PRABAL:** I also pushed a config fix earlier.

**SENTINEL:** I couldn't verify that one on GitHub — I don't see a matching commit from you. Is it on another branch, or still local?

---

## PER-PERSON CUE CARDS (each person's own lines only)

### VIJAY (Incident Commander)
1. "Okay everyone, payments are failing in production… I'm declaring this a SEV-1 and pulling in Sentinel."
2. "Good. Ankita, you're on monitoring — what are you seeing?"
3. "How bad on the customer side?"
4. "Okay, pool exhaustion is real. What changed? Did something ship recently?"
5. "This is exactly the point — the AI proposes, a human decides. I'm approving the revert." [Approve]
6. "While that redeploys — Sentinel opened a *real* pull request on GitHub and merged it."
7. "Everything on this board is evidence-backed… root-cause confidence only climbed *after* we confirmed the causal change."
8. "See the deploy version change up top — that's the real service redeploying, not a mock."
9. "That's Sentinel… never touched production without me. And it's already written the postmortem."
10. "One AI teammate — in the room, on voice, Slack, GitHub and Jira… Thank you."

### ANKITA (SRE)
1. "It's bad. Payment success rate has collapsed — around twenty percent. The database connection pool is pinned at a hundred percent. This is not a blip."
2. "Checkout is failing for most users right now. The support queue is climbing fast."
3. "I'm looking right at it — connections are maxed and payments are timing out waiting for the pool. The app looks up because it's accepting requests, but they're failing downstream."
4. "And it posted the whole thing to Slack, so the folks who aren't on this call are already in the loop."
5. "It's recovering — success rate is climbing back, the pool is draining, payments are going through again."

### PRABAL (Backend)
1. "Hmm, but the application side looks fine to me. My queries are returning, the service isn't actually down."
2. "…that's mine. I pushed the retry-logic change last night to fix the checkout timeouts. I completed it and merged it."
3. "Yeah… that would do it."
4. "Let's revert it. Roll it back to the previous version."
5. "That's the part I like — it didn't guess. It verified."

---

*Every Sentinel line corresponds to behavior the engine actually produces. See
`docs/DEMO_SCRIPT.md` for the full version with pre-flight checklist, stage directions,
timing table, and failure-mode fallbacks. See `CONTEXT.md` for the full project context.*
