# SENTINEL — 5-MINUTE WAR-ROOM DEMO SCRIPT

**Cast**
- **Vijay Singh** — Incident Commander (coordinates, gives the rollback approval)
- **Prabal Verma** — Backend Engineer (author of the change that broke it; proposes the fix)
- **Ankita** — SRE / Monitoring (raises the alarm, creates the conflict, confirms recovery)
- **Sentinel** — the AI (speaks in Kabir's voice; also posts to Slack)

**Three screens on the projector**
1. **War Room** (dark dashboard) — the main screen
2. **PayFlow status page** (`https://demo-payment-service.onrender.com/`) — the customer view
3. **Slack `#all-sentinel`** — the async chatter

**Speaking split**: Vijay ~30%, Ankita ~35%, Prabal ~25%, Sentinel ~10% (but Sentinel is the star between lines).

---

## PRE-FLIGHT (do this BEFORE you present — clock not running)

1. `cd sentinel && ./start.sh` — backend, frontend, ngrok up. Confirm
   `curl -s localhost:8000/health` → `{"ok":true}` and the ngrok URL responds.
2. Confirm `MONITOR_URL` in `backend/.env` = the Render URL, backend restarted.
3. Start load so the service is **already degrading** when you open (Option B — realistic):
   `while true; do for i in $(seq 1 40); do curl -s -m5 -X POST https://demo-payment-service.onrender.com/pay -o /dev/null & done; wait; done`
   Wait ~90s until the status page shows red "Major outage" (pool 100%, success ~20%).
4. Open the PayFlow status page in a browser tab (also wakes it from cold start).
5. Slack `#all-sentinel` already has the pre-incident standup thread (Prabal shipped the
   retry fix, Ankita's dashboards live, Vijay watching). Scroll to the bottom.
6. Sign in to the dashboard as Vijay. Have the **Declare** form ready with repo
   `NerdNinzas/demo-payment-service`. Everyone who's speaking should have the war-room
   tab open and be ready to **Join voice** (use headphones to avoid echo).

> If the Render service ever shows 100% healthy, it just means the load stopped — restart
> the load loop and wait ~60–90s.

---

## THE SCRIPT (0:00 → 5:00)

### BEAT 1 — Cold open + Sentinel joins  (0:00–0:35)

**[Vijay]** *(to the room, tapping the projector)*
> "Okay everyone — payments are failing in production. Support's getting complaints, our
> status page is red. I'm declaring a SEV-1 and pulling in Sentinel."

*(Vijay clicks **Declare SEV-1**, repo already set → the war room opens. He clicks
**Invite Sentinel** and everyone clicks **Join voice**.)*

**[Sentinel — spoken, on join]**
> "Sentinel here. I've joined the room and linked the payment-service repo. I'm tracking
> facts, hypotheses, actions and conflicts, and I'll only speak when it helps."

*(On screen: the timeline shows `🔗 Linked NerdNinzas/demo-payment-service` and
`🗂 Jira KAN` snapshot. Point at it: "It's already read our GitHub and Jira.")*

---

### BEAT 2 — Ankita raises the alarm (SRE)  (0:35–1:20)

**[Ankita]** *(urgent)*
> "I've been watching the dashboards — payment success rate has collapsed, we're down
> around twenty percent. And the database connection pool is completely pinned, it's at
> a hundred percent utilization. This is not a blip."

**[Sentinel — spoken]**
> "Confirmed from monitoring: payment success rate is critically low and DB connection
> utilization is at a hundred percent. I've recorded customer impact and flagged
> pool exhaustion as the leading hypothesis."

*(On screen: point at the **StatusPanel** — the live sparklines and the red tiles — and
the **State panel**: a Fact and a Hypothesis just appeared. "Notice it filed the metric
as a fact with monitoring evidence, and the theory as a hypothesis — not the same
bucket.")*

**[Vijay]**
> "How bad on the customer side?"

**[Ankita]**
> "Checkout is failing for most users right now. Support's queue is climbing."

---

### BEAT 3 — Prabal's theory + the CONFLICT  (1:20–2:05)

**[Prabal]** *(a bit defensive)*
> "Hmm — the application side looks fine to me though. My queries are returning, the
> service isn't down."

**[Sentinel — spoken, WARN]**
> "I want to flag conflicting information about database health. Ankita reports the
> connection pool is at a hundred percent, but Prabal says the application side looks
> fine. Can someone verify the current state before we treat this as settled?"

*(On screen: point at the **Conflicts** tab — a conflict card with both claims. "It
didn't pick a side. It asked us to verify. That's the honesty we want in an incident.")*

**[Ankita]** *(checking)*
> "I'm looking right at it — connections are maxed, and payments are timing out waiting
> for the pool. The app looks up because it's *accepting* requests, but they're failing
> downstream."

**[Sentinel — spoken]**
> "Understood — monitoring supports Ankita. The pool-exhaustion hypothesis is now
> confirmed by telemetry."

*(State panel: the hypothesis flips to **confirmed** with a green ring. The conflict
resolves.)*

---

### BEAT 4 — Evidence + CLAIM VERIFICATION  (2:05–2:55)

**[Vijay]**
> "Okay, pool exhaustion is real. What changed? Did something ship recently?"

**[Sentinel — spoken]**
> "One recent change correlates. On the payment-service repo, commit eight-three-seven-c
> by Prabal-verma — 'retry gateway timeouts' — was pushed shortly before this started. I
> flagged it as suspect."

*(On screen: point at the **RepoPanel** — commit `837c250` highlighted orange with a
**SUSPECT** badge. "It pulled our actual GitHub history in as evidence.")*

**[Prabal]** *(realizing)*
> "…that's mine. I pushed the retry-logic change last night to fix the checkout timeouts.
> I completed it and merged it."

**[Sentinel — spoken, SUMMARIZE]**
> "Verified — I can see Prabal-verma's commit eight-three-seven-c on the repo, and Jira
> ticket KAN-eleven, the retry-logic task, is marked Done. Your change checks out, Prabal.
> And that same retry change is exactly what correlates with the connection-pool leak —
> each retry grabs a new connection and doesn't release it on timeout."

*(Point at the timeline: `🔎 Checked Jira for Prabal: KAN-11 Done` and the ✅ Verified
fact. "It cross-checked GitHub AND Jira. It's not taking anyone's word for it — it
verified the claim, then correlated it with the outage.")*

---

### BEAT 5 — Propose → HUMAN APPROVAL  (2:55–3:25)

**[Prabal]**
> "Then let's revert v4.2. Roll it back to the previous version."

**[Sentinel — spoken, PROPOSE]**
> "Reverting a production deployment is an action I won't take on my own. I've prepared a
> revert of commit eight-three-seven-c and queued it for approval. Vijay, as incident
> commander, please approve or reject it on the dashboard."

*(On screen: the big red **HUMAN APPROVAL REQUIRED** modal appears — `open_revert_pr`,
the args, "Sentinel will not execute this without you." Let it sit for a beat.)*

**[Vijay]** *(to the room, then clicking)*
> "This is the whole point — the AI proposes, a human decides. I'm approving the revert."

*(Vijay clicks **Approve as Vijay**.)*

**[Sentinel — spoken]**
> "Vijay approved the revert. Opening and merging the pull request now, and watching for
> recovery."

---

### BEAT 6 — The redeploy wait (fill with narration)  (3:25–4:15)

*(The revert PR is merged; Render is auto-redeploying — ~40–90s. Use the time to show off,
don't stand in silence.)*

**[Vijay]** *(narrating over the three screens)*
> "While that redeploys — look at what just happened. Sentinel opened a **real** pull
> request on GitHub and merged it."

*(Switch to the **GitHub** tab briefly — show the merged revert PR.)*

**[Ankita]**
> "And it posted the whole thing to Slack — the team that's not in this call is fully in
> the loop."

*(Switch to **Slack `#all-sentinel`** — Sentinel's `🤖` status posts are there.)*

**[Vijay]** *(back to the war room)*
> "Everything on this board is evidence-backed. The confidence matrix says it plainly —
> high confidence on customer impact and the pool exhaustion, but notice root-cause
> confidence only rose *after* we confirmed the causal change. It never pretended to know
> more than it did."

*(Point at the **EvidenceGraph** and the **Confidence matrix** bars.)*

---

### BEAT 7 — RECOVERY  (4:15–4:45)

*(The status page flips. Switch to the **PayFlow status page** tab.)*

**[Ankita]** *(watching it)*
> "It's recovering — success rate is climbing back up, the connection pool is draining.
> Payments are going through again."

*(On the status page: the banner turns **green "All systems operational"**, the chart
climbs, and the **deploy SHA chip changes** to the revert commit. Point at the SHA:
"That's the deploy actually changing — this is the real service, not a mock.")*

**[Sentinel — spoken, SUMMARIZE]**
> "Payment success has recovered and the connection pool is back to normal. The incident
> appears resolved. Root cause: the v4.2 retry change leaked database connections under
> load; it was reverted via an approved pull request. I've filed the follow-ups."

---

### BEAT 8 — Wrap + the report  (4:45–5:00)

**[Vijay]**
> "That's Sentinel. It listened, separated what we knew from what we guessed, caught the
> conflict, verified Prabal's change against GitHub and Jira, and never touched production
> without me. And it's already written the postmortem."

*(Click **Report**. Show the incident report: impact, confirmed findings with evidence,
the decision ledger with Vijay's approval, actions by owner, the real PR link, unresolved
risks, confidence. End on it.)*

**[Vijay]**
> "One AI teammate, in the room, on voice, Slack, GitHub and Jira — turning a chaotic
> outage into a shared, evidence-backed source of truth. Thank you."

**[END — 5:00]**

---

## OPTIONAL BEATS (if you have extra time or want more wow)

- **Hinglish moment** (shows multilingual voice): Vijay asks *"Sentinel, abhi status kya
  hai?"* → Sentinel answers in natural Hinglish with the real numbers. Slots into Beat 2
  or 4.
- **Catch a bluff** (shows verification's teeth): a fourth voice (or Prabal) claims *"I
  also deployed the config fix"* with no matching commit → Sentinel: *"I couldn't verify
  that on GitHub — is it on another branch, or still local?"* Slots into Beat 4.
- **Overdue-action chase** (shows coordination): if an owner goes quiet, Sentinel
  proactively asks *"Ankita, do we have an update on the monitoring check?"* — happens on
  its own if you pause.

---

## TIMING CHEAT-SHEET

| Beat | Time | Who leads | Feature shown |
|---|---|---|---|
| 1 Cold open + join | 0:00–0:35 | Vijay | Agora voice, repo+Jira link |
| 2 Alarm + impact | 0:35–1:20 | Ankita | fact vs hypothesis, live telemetry |
| 3 Conflict | 1:20–2:05 | Prabal vs Ankita | conflict detection, WARN |
| 4 Evidence + verify | 2:05–2:55 | Prabal | GitHub suspect commit + claim verification (GitHub+Jira) |
| 5 Propose + approve | 2:55–3:25 | Vijay | human-in-the-loop approval gate |
| 6 Redeploy narration | 3:25–4:15 | Vijay/Ankita | real PR merged, Slack, evidence graph, confidence |
| 7 Recovery | 4:15–4:45 | Ankita | real service recovery, status page flips, SHA changes |
| 8 Wrap + report | 4:45–5:00 | Vijay | auto postmortem |

---

## FAILURE-MODE FALLBACKS (if something misbehaves live)

- **No TTS / voice silent** → check the agent-audio chip in the VoiceBar; click the
  autoplay-unblock button; worst case the browser TTS fallback still speaks. Keep going —
  the on-screen state is the real proof.
- **Gemini 429 / model error** → the rule extractor takes over automatically; the demo
  still runs (slightly less fluent phrasing). If it 404s on the model, it's a deprecation —
  not fixable mid-demo, rely on the rule path.
- **ngrok down** (voice/agent won't start) → a 404 from the ngrok URL means restart the
  tunnel. If you can't, run the **scripted offline demo** instead: on the incident, click
  **Run payment-outage demo** — it drives the whole arc through the pipeline with the
  built-in cast, and you narrate.
- **Render still healthy** (bug not manifesting) → the load loop stopped; restart it and
  wait ~60–90s, or just click **Attempt a payment** on the status page a few times to
  show a live failure.
- **Approval modal doesn't fire** → someone can type the revert intent in the transcript
  box or Slack; or trigger `open_revert_pr` from the tools path. The approval step is the
  crux — make sure a human clicks Approve on camera.

---

*This script maps 1:1 to the verified pipeline. Every Sentinel line corresponds to
behavior the engine actually produces (see CONTEXT.md §14 verification, §11 intervention
engine, §13 gateway). Rehearse once end-to-end before the real run.*
