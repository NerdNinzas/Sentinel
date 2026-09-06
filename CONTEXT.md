# SENTINEL — FULL PROJECT CONTEXT

> **Read this end-to-end before doing anything.** This is the complete, current
> state of the project so any Claude instance (or human) can continue without
> re-discovering everything. It is long on purpose. Keep it updated when you
> change architecture, integrations, credentials, or the demo plan.
>
> Companion file: `CLAUDE.md` (shorter quick-reference in the same folder). If the
> two ever disagree, trust whichever was edited most recently and reconcile them.
>
> Secrets policy: this file is inside the git repo, so it deliberately does **NOT**
> contain full API tokens/keys. Real secrets live in `sentinel/backend/.env`
> (gitignored). Where a secret is needed, this file says "see backend/.env" and,
> where safe, includes only non-secret identifiers (app IDs, account IDs, logins,
> commit SHAs, ports, channel IDs).

---

## TABLE OF CONTENTS

1. TL;DR — what this is in 60 seconds
2. The hackathon and the problem statement
3. Product vision and the one non-negotiable principle
4. Who is building it and the demo cast (Vijay, Prabal, Ankita)
5. Directory / repository layout
6. The five-layer architecture
7. How a single sentence flows through the system (voice, Slack, typed)
8. The incident state model (every entity)
9. The extractor: LLM path + rule path + the full op vocabulary
10. Deterministic engine rules (things the LLM is NOT allowed to decide)
11. The intervention engine (when/whether Sentinel speaks)
12. The confidence matrix
13. The tool gateway and every registered tool
14. Claim verification (GitHub + Jira cross-checking)
15. Integrations — every one, in detail, with gotchas and verified facts
    - 15.1 Agora (RTC + Conversational AI Engine + RTM)
    - 15.2 LLM (Gemini via OpenAI-compat)
    - 15.3 Cartesia TTS (the voice)
    - 15.4 Slack (read + write + customize)
    - 15.5 Jira
    - 15.6 GitHub (evidence + real revert PRs)
    - 15.7 MongoDB (persistence)
    - 15.8 Resend (email invites)
    - 15.9 ngrok (the tunnel)
16. Auth, organizations, invitations, onboarding, the guided tour
17. The frontend (every route and component)
18. The demo repo: `NerdNinzas/demo-payment-service` (PayFlow)
19. The full demo runbook (step by step, timed)
20. What has been verified working (test evidence)
21. Known issues, gotchas, and model/version churn
22. How to run everything locally
23. Environment variable reference (full `.env` shape)
24. Credentials inventory (where each lives; rotate after hackathon)
25. Pending / next steps / nice-to-haves
26. Working agreements (READ THIS — never push/commit, etc.)
27. Command cheat-sheet

---

## 1. TL;DR — WHAT THIS IS IN 60 SECONDS

**Sentinel — AI Incident Commander**, built by **NerdNinzas** for the **EchoSphere
hackathon** (Agora Conversational AI track; problem statement: *"Voice AI Incident
Commander"*).

Sentinel is a real-time AI teammate that **joins an incident war room** (voice +
Slack + a live dashboard) during a production outage. It:

- listens to everyone (voice via Agora, messages via Slack, typed text via the UI),
- turns the conversation into a **structured incident state** — separating **facts**
  (evidence-backed) from **hypotheses** (beliefs),
- tracks **actions with owners** and chases them when they go stale,
- detects **conflicts** between responders and asks for verification without picking
  a side,
- pulls the linked **GitHub** repo's recent commits/PRs as **evidence** and flags a
  suspect change,
- **verifies claims**: when someone says "I pushed the fix", it checks GitHub (real
  commit?) and Jira (ticket status?) and calls out discrepancies,
- computes a **confidence matrix** (customer impact, root cause, recovery, …) from
  state — never asserted by the model,
- **speaks** into the room only when it helps (WARN / ASK / SUMMARIZE / PROPOSE /
  CLARIFY), in English, Hindi, or Hinglish,
- and — the safety spine — **never runs a production action without a human**:
  rollbacks/reverts are proposed, blocked at a gateway, and require an incident
  commander to approve in the UI. Safe actions (Slack posts, Jira tickets) auto-run.

The killer end-to-end moment: a **real deployed payment service** breaks under load
(a planted connection-pool leak), Sentinel fingers the suspect commit, a human
approves a rollback, Sentinel **opens and merges a real GitHub revert PR**, the
deploy platform (Render) auto-redeploys, and the service **actually recovers** — all
visible live on a public status page. No mocks in that chain.

Pitch line: *"the missing intelligence layer inside the incident room."*

---

## 2. THE HACKATHON AND THE PROBLEM STATEMENT

**Event:** EchoSphere — an Agora Conversational AI hackathon. Build voice-native AI
that holds natural conversations, handles interruptions, remembers context, calls
external tools, and takes meaningful real-time actions.

**Chosen problem statement — "Voice AI Incident Commander":** Build a real-time AI
incident commander that joins a live operational/technical incident room. It should:
- participate in real time in a team voice room,
- recognize participant roles,
- extract facts, hypotheses, decisions, action items,
- assign and track task ownership,
- detect missing or conflicting information,
- maintain a continuously updated incident timeline,
- integrate with tools like Jira, Slack, PagerDuty, or monitoring,
- give spoken status summaries at appropriate moments,
- require human confirmation before executing critical actions,
- produce a final incident summary with unresolved risks.

Example scenario from the brief: a payment system outage where engineers, support,
and business leaders share incomplete/conflicting information; the AI organizes the
evidence, tracks responsibilities, and keeps the team aligned **without pretending to
independently determine root cause**. We implemented exactly this scenario.

The original long-form PRD (product requirements) the user wrote describes the full
vision: a state model of FACT / OBSERVATION / HYPOTHESIS / DECISION / ACTION /
UNKNOWN / CONFLICT / RISK, an evidence graph, an incident confidence matrix, a
decision ledger, an AI intervention engine, human-in-the-loop safety, and tool
integrations. Sentinel implements all of these.

---

## 3. PRODUCT VISION AND THE ONE NON-NEGOTIABLE PRINCIPLE

**The single most important design principle:** *the AI must distinguish what the
team KNOWS from what it BELIEVES.* Every piece of incident information lands in a
typed bucket. A hypothesis never silently becomes a fact. A metric number is a fact
with monitoring evidence; a participant's opinion is an observation or a hypothesis.
Root cause confidence stays low until a causal hypothesis is confirmed by evidence
AND humans.

**The second spine: human-in-the-loop for anything dangerous.** The LLM never calls a
production API. It *proposes* a tool; a gateway classifies it safe vs critical;
critical tools are blocked until a human approves in the UI. Policy is re-checked at
execution time; a unit test asserts a critical tool can never auto-run.

**Why this positioning wins:** existing tools (PagerDuty, Opsgenie, Jira) manage
alerts, tickets, and workflows. They do not participate in the live conversation or
maintain a shared, evidence-backed understanding. Sentinel manages *the conversation
and the shared understanding*. It does not say "I know the root cause"; it says "here
is what we know, here is what we believe, here is what conflicts, here is what we
don't know, here is who owns what, and here is what needs to happen next."

---

## 4. WHO IS BUILDING IT AND THE DEMO CAST

**Team:** NerdNinzas. Primary user/operator is **Vijay** (email in the harness
context: aatif.pmb@gmail.com; also uses rockcodingrookie21@gmail.com for the Atlassian
account). The user's UI/design preferences: noir/orange editorial theme, split-flap
hero, mono labels, numbered sections, readable (not too-dim) text, custom dropdowns
(no native selects), real brand icons.

**The three-person demo cast and their roles:**

| Person | Role | Where they exist | Identity details |
|---|---|---|---|
| **Vijay Singh** | Incident Commander (approves rollbacks; coordinates) | Slack (owner acct), Jira (nerdninzas) | Slack user `U0BV22PTJ94` (display "Sentinel", is_owner). Jira accountId `712020:ba45d7a3-bae5-4915-86f4-b0da3e783753` (display "nerdninzas", rockcodingrookie21@gmail.com) |
| **Prabal Verma** | Backend Engineer (authored the bad commit; proposes/does the fix) | Slack, Jira, GitHub | Slack `U0BV6J1CVDL`. Jira accountId `712020:deffcf19-f2fb-428f-b43f-b8e171ea44c3`. GitHub login `Prabal-verma`, id `122899996`. Classic PAT (repo scope) is in backend/.env as GITHUB_TOKEN |
| **Ankita** | SRE / Monitoring (raises alarm, creates conflict, confirms recovery) | Slack only (NOT in Jira/GitHub) | Slack `U0BUR9N1UET`. Email hidden in Slack, so cannot be invited to Jira yet |

**Role → feature mapping (each person triggers a different Sentinel capability):**
- Vijay (IC) → **human approval gate** (approves the revert).
- Prabal (Backend) → **GitHub claim verification** (his commit `837c250` is the leak;
  "I pushed the retry change" gets verified as true, then correlated with the outage).
- Ankita (SRE) → **conflict detection** (she says pool is at 100% while Prabal says
  the app side looks fine → Sentinel WARNs) and **recovery confirmation**.

Sentinel itself is a Slack bot (app user `U0BV2689938`, display "Sentinel", is_bot)
and an Agora agent (a real participant in the voice channel).

---

## 5. DIRECTORY / REPOSITORY LAYOUT

```
/Users/vijaysingh/Desktop/agora/
├── sentinel/                      ← MAIN REPO (git; remote origin = https://github.com/NerdNinzas/Sentinel.git, NOT pushed yet — user pushes)
│   ├── CONTEXT.md                 ← THIS FILE
│   ├── CLAUDE.md                  ← short quick-reference
│   ├── README.md
│   ├── start.sh                   ← one-shot: backend :8000 + frontend :3000 + ngrok; logs in .logs/
│   ├── .logs/                     ← backend.log, frontend.log, ngrok.log (gitignored-ish; runtime)
│   ├── docs/                      ← ARCHITECTURE.md (deep dive), AGORA.md, ROADMAP.md
│   ├── backend/                   ← FastAPI, Python 3.12, uv package manager. Entry: main.py
│   │   ├── main.py                ← app wiring, lifespan: db.connect + rehydrate incidents + engine.start
│   │   ├── pyproject.toml         ← deps (fastapi, uvicorn, pydantic, motor, httpx, openai, ...)
│   │   ├── pytest.ini
│   │   ├── .env                   ← ALL REAL SECRETS (gitignored)
│   │   ├── .env.example           ← template
│   │   ├── sentinel.db            ← legacy sqlite (unused now; Mongo is the store)
│   │   ├── tests/                 ← test_scenario.py, test_verify.py
│   │   └── app/
│   │       ├── core/
│   │       │   ├── config.py      ← pydantic-settings; reads .env
│   │       │   ├── agora.py       ← Agora Conversational AI Engine REST client (join/leave/speak/interrupt/query)
│   │       │   ├── token.py       ← Agora RTC/RTM AccessToken2 builder
│   │       │   ├── access_token2.py + Packer.py  ← vendored Agora AccessToken2 ('007') implementation
│   │       │   ├── db.py          ← MongoDB (motor): users, orgs, invites, sessions, memberships, incidents + write-behind snapshots
│   │       │   ├── auth.py        ← session cache + GitHub user lookup + oauth exchange
│   │       │   ├── accounts.py    ← email/password (pbkdf2), orgs, invites, onboarding
│   │       │   └── mailer.py      ← Resend email (invite HTML template)
│   │       ├── engine/
│   │       │   ├── models.py      ← the incident state model (Pydantic)
│   │       │   ├── store.py       ← in-memory IncidentStore + WebSocket event bus + apply_ops (the op applier)
│   │       │   ├── extractor.py   ← LLM extractor + RuleExtractor (regex), the op vocabulary
│   │       │   ├── engine.py      ← the orchestrator (tick loop, speech decisions, follow-ups, slack loop, live monitor, loadgen, verify_claim, link_repo, link_jira, agent lifecycle, scripted scenario)
│   │       │   ├── confidence.py  ← confidence matrix (computed from state)
│   │       │   └── report.py      ← final incident report (markdown) + spoken status summary
│   │       ├── tools/
│   │       │   ├── gateway.py     ← tool registry (safe/critical), propose/decide/execute, human approval
│   │       │   ├── adapters.py    ← Slack (r/w + history/users), Jira (create + read), PagerDuty, mock Deploy, re-export monitoring
│   │       │   └── github.py      ← fetch_changes (evidence), create_issue, comment_on_pr, open_revert_pr (REAL revert)
│   │       ├── llm/
│   │       │   ├── client.py      ← OpenAI-compatible client (Gemini via compat endpoint); complete_json / complete_text
│   │       │   └── prompts.py     ← SENTINEL_PERSONA, EXTRACTION_SYSTEM, REPORT_SYSTEM
│   │       ├── mock/
│   │       │   ├── monitoring.py  ← mock monitoring + ingest_live (real telemetry) + query API
│   │       │   └── scenario.py    ← scripted PRD payment-outage demo (works fully offline)
│   │       └── api/
│   │           ├── incidents.py   ← REST: create/join/transcript/decide/agent start-stop/demo/end/delete/report/config/repo
│   │           ├── auth.py        ← REST: signup/login/onboard/me/notice-ack/org/invites/integrations/github connect/oauth
│   │           ├── agora_llm.py   ← /v1/chat/completions (the "custom LLM" Agora calls)
│   │           └── ws.py          ← WebSocket /ws/incidents/{id}
│   └── frontend/                  ← Next.js 16, Tailwind v4, noir/orange theme (Anton + IBM Plex Mono + Inter)
│       ├── package.json           ← pnpm; deps: agora-rtc-sdk-ng, agora-rtm, zustand, framer-motion, recharts, lucide-react, react-markdown, remark-gfm, playwright-core (dev)
│       ├── scripts/               ← *.mjs headless-Chrome driver scripts for screenshots/verification
│       └── src/
│           ├── app/
│           │   ├── page.tsx                       ← landing (public; hero, signals, pipeline, war-room CTA)
│           │   ├── login/page.tsx                 ← email/password sign in + sign up
│           │   ├── dashboard/page.tsx             ← sidebar console (overview, war rooms, integrations, team, profile, settings) + onboarding modal + tour
│           │   ├── invite/[token]/page.tsx        ← accept-invite page
│           │   ├── incident/[id]/page.tsx         ← the WAR ROOM
│           │   └── incident/[id]/report/page.tsx  ← final report
│           ├── components/        ← Header, StatusPanel, Participants, Timeline, StatePanel, Transcript, ApprovalModal, VoiceBar, SentinelBanner, EvidenceGraph, RepoPanel, Select (custom dropdown), onboarding (modal+tour), ui (icons/avatars/rings/sparklines/brand icons)
│           ├── hooks/useAgoraRoom.ts   ← RTC join + RTM transcript forward + browser STT/TTS fallback + agent audio state + autoplay unblock
│           ├── store/useIncident.ts    ← zustand store fed by one WebSocket; metric history for sparklines
│           └── lib/
│               ├── api.ts         ← session-bearer fetch client (all backend calls)
│               ├── types.ts       ← TS mirror of the backend state model
│               └── utils.ts       ← cn, time formatting, avatar colors, initials, tone
└── demo-payment-service/          ← SEPARATE REPO (pushed to github.com/NerdNinzas/demo-payment-service)
    ├── README.md                  ← sanitized (does NOT reveal the planted bug)
    ├── render.yaml                ← Render deploy config (auto-deploy on push to main)
    ├── requirements.txt
    └── src/
        ├── app.py                 ← FastAPI: / (status page), /health, /logs, /pay
        ├── db.py                  ← bounded connection pool (asyncio.Semaphore, size 20)
        ├── gateway.py             ← simulated card gateway (times out ~8% of calls)
        ├── payments.py            ← process_payment — THE FILE WITH THE PLANTED LEAK at HEAD
        ├── metrics.py             ← windowed success-rate metric
        ├── logbuf.py              ← in-memory ring buffer of log lines (served at /logs)
        └── statuspage.py          ← the public "PayFlow" status page HTML (served at /)
```

---

## 6. THE FIVE-LAYER ARCHITECTURE

Think of it as body / brain / memory / hands / face:

| Layer | Tech | Role | Reasoning? |
|---|---|---|---|
| **Voice (body)** | Agora RTC + Conversational AI Engine + RTM | Voice room; speech→text (ares ASR); turn detection; interruption/barge-in; text→speech (Cartesia); transcript delivery | ❌ none — pure signal processing |
| **Brain** | Gemini 3.5 Flash-Lite via our backend | Reads transcript + state, emits typed ops (this is a hypothesis, that's an action, these conflict); decides WAIT vs speak and the sentence | ✅ interpretive reasoning |
| **Memory** | IncidentStore (in-memory Pydantic) + WebSocket bus + MongoDB snapshots | The single source of truth; every mutation via apply_ops; broadcast to UI; persisted and rehydrated | ✅ deterministic rules + safety |
| **Hands** | Tool Gateway + adapters | The only path from AI to external APIs (Slack/Jira/GitHub/monitoring/deploy) | ✅ policy + human approval |
| **Face** | Next.js + zustand + Agora Web SDKs | War-room dashboard; one WebSocket feeds one store | — |

**The key trick that wires Agora to our brain:** when we start the Agora agent we set
`llm.vendor: "custom"` and `llm.url` = our backend's `/v1/chat/completions` (reached
through the ngrok tunnel). So Agora *thinks* it is calling an LLM the way it would
call OpenAI — but it is actually reaching our incident engine, which consults Gemini,
updates the MongoDB-backed state, and streams back either silence or a short
utterance for Agora to voice.

**Honest one-liner for judges:** Agora is the ears, mouth, turn-taking, and speaker
identity; Gemini is the interpreter; our engine is the memory and judgment; and the
parts that must never hallucinate (metrics, confirmations, production actions) are
deterministic Python and a human gate — not the model.

---

## 7. HOW A SINGLE SENTENCE FLOWS THROUGH THE SYSTEM

### 7.1 Voice path (someone speaks in the room)

1. **Audio in.** A participant's mic → Agora RTC channel (`sentinel-inc-<id>`). The
   Sentinel agent (started via REST join, `remote_rtc_uids: ["*"]`) hears everyone.
2. **ASR + turn detection.** Agora's `ares` ASR transcribes (configured for
   `en-IN,hi-IN` so it handles English, Hindi, and Hinglish). Agora decides when the
   speaker finished (turn detection) and handles barge-in.
3. **Transcript arrives twice, on purpose:**
   - Over **RTM** as `user.transcription {user_id, text, final}` — this is the ONLY
     copy that carries the *speaker identity*. The dashboard's `useAgoraRoom` hook
     forwards final lines to `POST /api/incidents/{id}/transcript`.
   - Through the **custom-LLM callback**: Agora POSTs to our
     `/v1/chat/completions` — this copy is anonymous (no speaker) and, annoyingly,
     ACCUMULATES the turn's sentences. It is the "turn ended, you may reply" signal.
   - The backend de-duplicates the two copies (fuzzy similarity match) and, when
     there is exactly one human in the room, attributes the anonymous copy to that
     human.
4. **Tick.** `engine.tick()` takes pending lines + monitoring events since last tick →
   runs the extractor → applies ops to the store → runs deterministic state rules →
   recomputes the confidence matrix → produces an intervention decision.
5. **Reply or stay silent.** The `/v1/chat/completions` response STREAMS THE FIRST
   BYTE IMMEDIATELY (Agora abandons a slow-to-start LLM and silently drops the reply —
   this was a real bug we fixed). If the decision is WAIT, the streamed content is
   empty and the agent says nothing. Otherwise the sentence streams out and Cartesia
   voices it. Proactive speech (follow-ups, monitoring alerts) uses the Agora `speak`
   REST endpoint instead.
6. **Everyone sees it.** The store broadcasts a full state snapshot on every mutation;
   the dashboard swaps it in and React re-renders (timeline, state tabs, confidence,
   evidence graph, repo panel).

### 7.2 Slack path (someone types in #all-sentinel)

A background loop (`engine._slack_loop`) polls `conversations.history` every 4s during
a live incident. New human messages (bot/self/join-notices filtered out) are mapped
to the real user's name (matched to an existing war-room participant by first name if
they are also on voice), then fed through the SAME pipeline as voice. A timeline event
`💬 Slack #all-sentinel · <name>: "…"` is added so the room sees what Sentinel read.
When an incident has Slack participants, Sentinel's spoken interventions are also
echoed back into the channel as `🤖 …`.

### 7.3 Typed path (the dashboard transcript box)

`POST /api/incidents/{id}/transcript` with the signed-in user's uid — same pipeline.

### 7.4 Fallbacks (so the demo never hard-depends on anything)

- No Agora creds → the browser uses `SpeechRecognition` for input and
  `speechSynthesis` for output.
- No LLM key (or a 429) → the deterministic `RuleExtractor` produces the same op JSON.
- No Mongo → memory-only; everything still works, just no persistence/rehydration.

---

## 8. THE INCIDENT STATE MODEL (backend/app/engine/models.py)

Everything extracted lands in one of these buckets on the `Incident` object. Store
mutations go through `store.apply_ops` (typed ops emitted by the extractor) — never
free-form state rewrites.

- **Participant**: uid, name, role (incident_commander / sre / backend / frontend /
  database / security / support / product / business / observer / unknown), focus,
  role_source (declared / inferred / corrected), online.
- **Evidence**: source (monitoring / participant / tool / deployment / customer),
  summary, supports (bool; false = contradicts), by, at.
- **Fact**: text, evidence[], confidence, at. Evidence-backed; the team treats it as
  true.
- **Observation**: text, by, at. Something a participant reported; not yet verified.
- **Hypothesis**: text, proposed_by, status (unverified → investigating → confirmed /
  rejected), confidence, supporting[], contradicting[], last_verified. A hypothesis
  becomes CONFIRMED only when it has monitoring/tool evidence AND team agreement; on
  confirm it also becomes a Fact.
- **Decision**: seq, text, reason, participants[], approved_by, at. Immutable ledger.
- **Action**: text, owner (None = unowned; Sentinel chases), priority (critical/high/
  normal), status (open/in_progress/done/blocked), result, external_ref (e.g. Jira
  key). Owned actions start in_progress; stale ones get chased.
- **Conflict**: topic, claim_a/by_a, claim_b/by_b, status (open/resolved), resolution.
- **Unknown**: question, why_it_matters, status (open/answered), answer.
- **Risk**: text, severity (low/medium/high), status (open/mitigated).
- **TimelineEvent**: at, kind (incident/metric/hypothesis/fact/action/decision/
  conflict/unknown/risk/approval/tool/sentinel/participant/slack/jira), text, ref.
- **ToolProposal**: tool, args, reason, risk (safe/critical), approval (pending/
  approved/rejected/expired), approved_by, result, error.
- **ConfidenceMatrix**: customer_impact, outage_scope, primary_finding,
  change_correlation, root_cause, recovery (all 0..1, computed — never asserted).
- **TranscriptLine**: uid, name, text, at, final, turn_id.
- **Incident**: id (INC-xxxx), title, severity (SEV-1/2/3), status (investigating /
  identified / mitigating / recovered / resolved), channel, started_at, resolved_at,
  impact_summary, participants{}, transcript[], all the buckets above, metrics{},
  repo, repo_changes{}, agent_id, version (bumped on every mutation).

---

## 9. THE EXTRACTOR (backend/app/engine/extractor.py)

Two implementations with the same signature:

- **`llm_extract`** — sends the state digest + new lines to the model
  (`EXTRACTION_SYSTEM` prompt) and asks for JSON: `{"ops": [...], "intervention": {...}}`.
- **`RuleExtractor`** — regex/keyword rules for the same op set. Runs when there is no
  `LLM_API_KEY`, on any LLM failure (e.g. 429), and importantly on metric-only ticks
  (we skip the LLM when there are no new transcript lines to save quota).

### The full op vocabulary (what the model may emit)

```
add_observation {text, by}
add_fact {text, confidence, evidence:[{source, summary, by}]}
add_hypothesis {text, proposed_by, confidence}
update_hypothesis {id, status, confidence, evidence:{source, summary, by, supports}}
add_action {text, owner|null, priority, created_by}
update_action {id, status, result, owner}
add_decision {text, reason, participants:[], approved_by}
add_conflict {topic, claim_a, by_a, claim_b, by_b}
resolve_conflict {id, resolution}
add_unknown {question, why_it_matters}
answer_unknown {id, answer}
add_risk {text, severity}
set_role {uid, role, focus}
set_status {status}
set_impact {text}
propose_tool {tool, args, reason}
```

### Key extraction rules (in the prompt AND the regex engine)

- "I think / probably / suspect / might / could be" → `add_hypothesis`, NEVER
  `add_fact`.
- A monitoring number → a fact with monitoring evidence. A participant claim without
  data → an observation.
- "<Name>, check X" / "can someone look at X" → `add_action` (owner null if nobody
  named; Sentinel then chases for an owner).
- Owner reports a result → `update_action` done with result.
- A revert/rollback/restart/failover/scale/disable proposal → `propose_tool` (only
  when a human proposed it). When a GitHub repo is linked, `open_revert_pr` is
  preferred.
- Two statements disagreeing on the same topic → `add_conflict` (never pick a side).
- Commander agreement ("let's do it", "approved", "freeze deployments") →
  `add_decision`.
- Completion claims ("I've completed / pushed / deployed / merged …") →
  `update_action` done AND trigger `verify_claim` (see §14).

`intervention` = `{action: WAIT|ASK|WARN|SUMMARIZE|CLARIFY|PROPOSE, speech, urgency}`.
Special sentinel value `__STATUS__` → replaced by `report.status_speech(inc)`.

The rule extractor also does fuzzy wake-word matching because ares mangles the name
("sentinal / santenal / renal") and triggers on bare status questions ("what's the
status", "kya status hai") without needing the name.

---

## 10. DETERMINISTIC ENGINE RULES (things the LLM is NOT allowed to decide)

In `engine.py`, done in plain Python so the model can never hallucinate them:

- **Metrics → facts** (`_metric_rules`): "payment success rate dropped to 21%" and "DB
  connection utilization at 100%" become facts with `source: monitoring` evidence. The
  numbers come from the monitoring adapter, never the model.
- **Hypothesis evidence**: when DB utilization ≥ 95%, open hypotheses mentioning
  db/pool/connection get monitoring evidence and move to `investigating`.
- **Unknowns**: blast radius (regional?), auth affected?, "did the deploy cause it?",
  "is rollback safe?" are auto-added, and auto-answered when data arrives (e.g. auth
  success 99.6% → answered).
- **Recovery**: success rate crossing back above 95% → fact, `status: recovered`,
  risks ("root cause not conclusively established", "deployment correlation requires
  validation", "connection pool config needs review"), and safe follow-up tools
  (Slack status post, Jira ticket).
- **Conflict resolution**: once a pool/database hypothesis is confirmed, the
  "healthy vs 100%" conflict is resolved with an explanation.
- **Repo evidence** (`_repo_evidence_rules`): attaches the most suspect recent commit
  as `deployment`-source evidence to causal hypotheses.

---

## 11. THE INTERVENTION ENGINE (when/whether Sentinel speaks)

Every tick returns `{action, speech, urgency}` with action ∈ WAIT / ASK / WARN /
SUMMARIZE / CLARIFY / PROPOSE.

- WAIT → silence (the default when the conversation is productive).
- WARN → a conflict detected, or someone treating a belief as fact.
- ASK → a critical unknown blocks progress, or an action has no owner.
- SUMMARIZE → a major state change (hypothesis confirmed, recovery, status change).
- PROPOSE → an obvious, evidence-backed next step (says clearly it needs human
  approval if it is a production action).
- CLARIFY → someone addressed Sentinel directly.

A throttle (`MIN_GAP_S = 8`) suppresses non-urgent speech; `urgency: high` always goes
through with `priority: INTERRUPT` on the Agora speak API. A background **follow-up
loop** (every 10s) speaks proactively when an in-progress action is stale (>90s), an
action is unowned (>30s), or an approval has been pending (>45s).

---

## 12. THE CONFIDENCE MATRIX (backend/app/engine/confidence.py)

Six numbers computed FROM STATE, never asserted by the model: customer_impact,
outage_scope, primary_finding, change_correlation, root_cause, recovery.

- customer_impact: customer-sourced evidence + payment-success metric.
- outage_scope: metric-backed fact about the failing system.
- primary_finding: best non-rejected hypothesis confidence; discounted by open
  conflicts.
- change_correlation: best confidence among hypotheses about deploys/changes.
- **root_cause: only rises above ~0.45 when a CAUSAL hypothesis is CONFIRMED.** This is
  what lets Sentinel honestly say "high confidence on impact, low confidence on root
  cause."
- recovery: from the live payment success rate + status.

---

## 13. THE TOOL GATEWAY AND EVERY TOOL (backend/app/tools/gateway.py)

Flow: `LLM/rules → propose_tool → gateway.propose()`:
- risk = **safe** → execute immediately.
- risk = **critical** → create a pending `ToolProposal`, add a `🛑 approval required`
  timeline event, broadcast `approval_required` → the dashboard shows a red modal →
  human clicks Approve/Reject → `gateway.decide()` → writes a Decision ledger entry →
  `execute()`. Policy is RE-CHECKED at execution: a critical tool with an auto/policy
  approver is refused (test: `test_critical_tool_cannot_auto_execute`).

**Safe tools (auto-run):**
- `post_slack_update` — posts to #all-sentinel.
- `create_jira_ticket` — creates a real KAN ticket (now that Jira is live).
- `comment_on_pr` — comments on a PR of the linked repo.
- `github_recent_changes` — fetch recent commits/PRs.
- `recent_deployments` — (mock deployment list, legacy).
- `query_monitoring` — read a metric.
- `page_oncall` — PagerDuty (mock until creds).
- `create_github_issue` — open an issue on the linked repo.

**Critical tools (human approval required):**
- `open_revert_pr` — **REAL**: creates a revert commit (parent tree of the suspect
  commit) on branch `sentinel/revert-<sha>`, opens a PR, and merges it → deploy
  platform auto-redeploys → live recovery. Preferred when a repo is linked; auto-
  targets the suspect commit.
- `rollback_deployment`, `restart_service`, `failover_database`, `scale_service`,
  `disable_feature_flag` — mock deploy controller (drives the mock monitoring to
  recovery in offline demos).

---

## 14. CLAIM VERIFICATION (backend/app/engine/engine.py :: verify_claim)

When anyone (voice or Slack) says something like "I've completed / pushed / deployed /
merged the fix", the engine:

1. Detects the claim (regex over push/deploy/merge/completed patterns) OR the LLM
   marks the action done.
2. Resolves who they are on GitHub: their connected `github_login` from the user doc,
   else first-name match against commit author names.
3. **GitHub leg**: fetches the linked repo's recent commits (uses the COMMITTER date =
   push/merge time, not the author date which can be days old after a rebase), and
   matches an author within the configurable suspect window
   (`github_suspect_minutes`, default 2880 = 2 days for the demo).
   - Match → ✅ a fact: "Verified: <name>'s update matches GitHub — repo@sha 'msg' by
     <author>, N min ago"; the action gets `✅ verified · sha`; Sentinel speaks and
     posts to Slack: "Verified — I can see <author>'s commit <sha>… checks out."
   - No match → ⚠ a risk ("Unverified claim…") and a polite public callout: "<name>, I
     couldn't verify that on GitHub — is the push on another branch, or still local?"
4. **Jira leg**: looks up the person's assigned tickets; adds a timeline event
   "🔎 Checked Jira for <name>: KAN-x 'summary' · status"; if a not-done ticket exists
   it says "On Jira, KAN-x is still <status> — should it move?"; else "Jira agrees:
   KAN-x is Done."

The verified-vs-flagged behavior is covered by unit tests
(`test_claim_verified_when_commit_exists`, `test_claim_flagged_when_no_commit`).

---

## 15. INTEGRATIONS — EVERY ONE IN DETAIL

### 15.1 Agora (RTC + Conversational AI Engine + RTM)

- **App ID:** `5cd07183162c439c902b49ac8cb728de` (non-secret). App Certificate,
  Customer Key, Customer Secret are in backend/.env.
- **RTC:** humans join the voice channel from the dashboard (`agora-rtc-sdk-ng`).
  Tokens are AccessToken2 ('007'), built in `core/token.py` from the certificate.
- **Conversational AI Engine (REST v2):** `POST
  https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/join`, Basic
  auth (customer key:secret). We set `llm.vendor: "custom"`, `llm.url` =
  `{PUBLIC_BASE_URL}/v1/chat/completions`, so Agora calls our backend as its LLM.
  `agent_rtc_uid` from settings; `enable_string_uid: true`; `remote_rtc_uids: ["*"]`
  (subscribe to everyone); `advanced_features.enable_rtm: true`; `data_channel: "rtm"`.
  Agent `name` is `sentinel-<id>-<timestamp>` (unique per start to avoid 409 conflicts
  when restarting while the old agent winds down).
- **ASR:** `ares` (Agora's built-in), language `en-IN,hi-IN` (handles Hinglish
  code-switching).
- **TTS:** Cartesia (see 15.3). Passed in the `tts` block with `credential_mode`
  implied by supplying the api_key.
- **RTM:** `agora-rtm` on the client subscribes to the channel and forwards
  `user.transcription` messages (which carry `user_id`) to the backend for speaker
  attribution.
- **speak / interrupt / leave / query:** REST endpoints on
  `/agents/{agentId}/…`. `speak` body `{text (≤512 bytes), priority:
  INTERRUPT|APPEND|IGNORE, interruptable}`. Used for proactive speech (greetings,
  follow-ups, monitoring alerts) and the approval confirmation.
- **Gotchas learned the hard way:**
  - Managed TTS pool is flaky and SKU-limited (only openai+minimax on the free SKU),
    and had transient 500s ("model service temporarily unavailable"). We switched to
    **Cartesia with our own key** to bypass it. Join retries 3× with backoff for
    transient 500s.
  - The custom-LLM endpoint MUST stream the first byte instantly (Agora drops slow
    LLMs → text reaches the dashboard via our WS but never gets voiced). We fixed this
    by opening the SSE stream immediately and running the brain inside the stream with
    a 12s cap.
  - The join `name` must be unique per start (409 Conflict otherwise).
  - The custom-LLM callback copy of the transcript is anonymous and accumulates
    sentences → dedupe by similarity; attribute to the sole human when there's one.

### 15.2 LLM (Gemini via OpenAI-compat)

- **Current model:** `gemini-3.5-flash-lite` (see churn note below). Endpoint:
  `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`. Key in
  backend/.env (`LLM_API_KEY`).
- The client is OpenAI-compatible (`openai` python SDK pointed at the compat base
  URL), so it also works with OpenAI/Groq/OpenRouter/Ollama by changing base+model.
- **Model churn we hit (IMPORTANT):** Google is aggressively deprecating models.
  `gemini-2.5-flash` free tier = only **20 requests/day** (we blew through it →
  429s). `gemini-2.5-flash-lite` returned 404 "no longer available to new users →
  use gemini-3.5-flash-lite". So we are on `gemini-3.5-flash-lite`. **If you see 404
  on the model, read the error — it names the replacement — and update LLM_MODEL.**
  For demo day the free key is fragile; recommend a backup key on a second account or
  enabling billing (flash-lite is pennies). We also skip the LLM on metric-only ticks
  to conserve quota, and fall back to the rule extractor on any failure.

### 15.3 Cartesia TTS (the voice)

- **Vendor:** cartesia. **Model:** `sonic-3` (NOTE: Agora's docs say `sonic-2` but
  Cartesia SUNSETTED sonic-2 → sonic-3 is current; sonic-turbo also works).
- **Voice:** "Kabir" (Indian male), voice id `cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5`,
  language `hi`. Alternative female Indian voice "Siya" id
  `4459a9a5-69d6-4680-b970-e13dc51845b6` (one env-line swap).
- **Config in .env:** `AGORA_TTS_VENDOR=cartesia`, `AGORA_TTS_API_KEY=<cartesia key>`,
  `AGORA_TTS_PARAMS_JSON={"model_id":"sonic-3","base_url":"wss://api.cartesia.ai","voice":{"mode":"id","id":"cb9c954d-..."},"output_format":{"container":"raw","sample_rate":16000},"language":"hi"}`.
- Legal note: using Cartesia via your own key is a normal API-customer relationship;
  Agora is just the pipeline. Cartesia free tier is non-commercial (fine for a
  hackathon).
- Multilingual: the persona prompt tells the model to understand English/Hindi/
  Hinglish and reply in the room's language (technical terms stay English).

### 15.4 Slack (read + write + customize) — LIVE

- **Workspace:** the user's Slack (may be named "sentinel"/NerdNinzas). **Channel:**
  `#all-sentinel`, channel id `C0BV22Q3P1U`.
- **Bot token** (xoxb-…) in backend/.env. **Scopes:** `chat:write`, `channels:read`,
  `channels:history`, `users:read`, `chat:write.customize`.
- **Read:** `engine._slack_loop` polls `conversations.history` every 4s during live
  incidents; human messages → the pipeline; timeline shows `💬 Slack …`.
- **Write:** safe tool `post_slack_update`; Sentinel echoes interventions as `🤖 …`.
- **customize:** with `chat:write.customize` we can post AS specific people
  (username + icon_url = their real Slack avatar). Used to stage a realistic
  pre-incident standup thread as Vijay/Prabal/Ankita with their real profile photos.
- **Bookmarks/Canvas/Lists:** need `bookmarks:write` / `canvases:write` (NOT granted).
  Optional nice-to-haves; messages are the real incident surface.
- **Model:** org/workspace-level (one workspace per deployment, configured in .env).
  Multi-tenant "Add to Slack" OAuth is a documented future upgrade.
- **Cannot delete other users' messages** with a bot token (only its own) — cleaning
  the channel leaves un-deletable "X joined the channel" system notices.

### 15.5 Jira — LIVE

- **Site:** `https://nerdninzas.atlassian.net`. **Project key:** `KAN`. **Email:**
  `rockcodingrookie21@gmail.com`. **API token** in backend/.env
  (`JIRA_API_TOKEN`), Basic auth = email:token.
- **Jira users (assignable):** Prabal Verma `712020:deffcf19-f2fb-428f-b43f-b8e171ea44c3`;
  nerdninzas (=Vijay) `712020:ba45d7a3-bae5-4915-86f4-b0da3e783753`. **Ankita is NOT
  in Jira** (Slack only) — cannot be assigned until invited (need her email).
- **Workflow transitions:** To Do=11, In Progress=21, In Review=31, Done=41.
- **Current KAN board (rebuilt around the incident):**
  - KAN-11 "Add retry logic for gateway timeouts in payment processing" — Prabal —
    **Done** (the change that shipped = v4.2 / commit 837c250; the verification anchor).
  - KAN-12 "Optimize payment gateway integration latency" — Prabal — In Progress.
  - KAN-13 "[SRE - Ankita] Payment success-rate & DB pool monitoring dashboards" —
    unassigned — Done.
  - KAN-14 "[SRE - Ankita] Alerting on payment success-rate drop" — unassigned — In
    Progress.
  - KAN-15 "PAY-OUTAGE: Payment API degradation - DB connection pool exhaustion
    (SEV-1)" — nerdninzas/Vijay — In Progress.
  - KAN-16 "Revert v4.2 retry change leaking DB connections" — Prabal — To Do.
- **Read APIs used:** `open_issues` (project, statusCategory != Done),
  `issues_for(person)` (assignee search by name). Adapter: `tools/adapters.py :: Jira`.
- **Reading raw with curl:** the search endpoint is `/rest/api/3/search/jql?jql=…`.
- Sentinel snapshots the board into the timeline on incident creation
  (`engine.link_jira`), and cross-checks assignee status in `verify_claim`.

### 15.6 GitHub (evidence + real revert PRs)

- **Demo repo:** `NerdNinzas/demo-payment-service` (public). Sentinel's own repo:
  `NerdNinzas/Sentinel` (remote set, NOT pushed — user pushes).
- **Auth:** per-user (GitHub is an INTEGRATION on the dashboard, not the login). A
  classic PAT or OAuth attaches to a signed-in account. For the demo, **Prabal's
  classic PAT (repo scope)** is set as `GITHUB_TOKEN` in backend/.env — this is what
  `open_revert_pr` uses for write access. GitHub OAuth app client id/secret are also
  in .env (callback = ngrok URL).
- **Evidence:** `github.py :: fetch_changes(repo, incident_start, token)` returns
  recent commits (72h look-back), merged PRs, latest release, failed CI runs;
  a change within `github_suspect_minutes` of the incident is `suspect`. Uses the
  COMMITTER date for "push time".
- **Real revert:** `open_revert_pr(repo, sha, reason)` → creates a revert commit whose
  tree = the parent tree of the suspect commit, on branch `sentinel/revert-<sha7>`,
  opens a PR, merges it. Verified working against the live Render deploy.
- **Config:** `github_default_repo=NerdNinzas/demo-payment-service`,
  `github_suspect_minutes=2880`.

### 15.7 MongoDB (persistence) — LIVE

- **Atlas cluster,** database `Sentinel`. URI in backend/.env (`MONGODB_URL`).
- **Collections:** users (email/password hash, github_token/login, org membership),
  orgs, invites, sessions (bearer `st_…` tokens), memberships (who created/joined
  which incident), incidents (full state snapshots, write-behind every 2s).
- **Rehydration:** on startup, `main.py` loads recent incident snapshots back into the
  store, so rooms survive backend restarts.
- If Mongo is unreachable: memory-only mode; everything works, no persistence.
- A test session exists: token `st_testsession123` → user `999001` (login `vijay-dev`,
  onboarded, personal). Handy for scripted API tests.

### 15.8 Resend (email invites)

- `mailer.py`; key in backend/.env (`RESEND_API_KEY`, currently blank → mock). When
  set, org invitations email a branded HTML template. Default sender
  `onboarding@resend.dev` can only email yourself until a domain is verified in
  Resend.

### 15.9 ngrok (the tunnel)

- Reserved domain: `https://evaluatingly-unparcelling-andree.ngrok-free.dev` =
  `PUBLIC_BASE_URL`. Must be running for (a) the Agora custom-LLM callback and (b) the
  GitHub OAuth callback. `start.sh` launches it:
  `ngrok http --url=evaluatingly-unparcelling-andree.ngrok-free.dev 8000`.
- It drops sometimes; if OAuth or voice fails, check the tunnel first (a 404 HTML page
  from that URL = ngrok is down, not our code).

---

## 16. AUTH, ORGANIZATIONS, INVITATIONS, ONBOARDING

- **Email/password** signup+login (`accounts.py`, pbkdf2). Sessions are bearer `st_…`
  tokens (Mongo `sessions` + a process cache). `AUTH_REQUIRED=true` gates
  create/join. GitHub is NOT the login anymore — it's an integration.
- **Onboarding modal** on first dashboard visit: **personal** vs **organization**.
  Organization asks name/address/website → creates an `orgs` doc, creator = owner.
- **Guided tour**: a 5-step tooltip walkthrough (Overview → War Rooms → Integrations →
  Team → Settings) after onboarding; localStorage flags so it shows once.
- **Invites**: `POST /org/invites {email?}` → token + link `/invite/<token>`. Email
  sent via Resend when configured (mock otherwise; the link always works). Accepting
  joins the org, sets an `org_notice` ("You have been added to X" banner), and both
  members then see each other on the Team page. Verified end-to-end with two browser
  sessions.
- **GitHub connect**: per-user PAT paste or OAuth
  (`/api/auth/github/login?session=…` attaches to the signed-in account). Powers
  private-repo evidence, the repo dropdown, and revert PRs.

---

## 17. THE FRONTEND (every route and component)

Theme: **noir/orange editorial** — near-black graphite panels on `#101114`, orange
(`#f97316`) as the single accent, IBM Plex Mono labels with wide tracking, Anton for
display headings, Inter for body. Split-flap hero on the landing page. Film-grain +
faint grid background. Custom dropdowns (no native selects). Real brand SVG icons for
Slack/Jira/GitHub. Theme was deliberately brightened once (text was too dim).

- **/ (landing, public):** split-flap "SENTINEL" hero; numbered sections 01/SIGNALS
  (feature cards), 02/PIPELINE (life of a sentence), 03/WAR ROOM (declare form).
  Homepage is NOT gated; clicking join/declare when signed out routes to /login.
- **/login:** SIGN IN / SIGN UP tabs; email + password. Handles a pending-invite
  handoff (accept after signup).
- **/dashboard:** the operator console with a fixed sidebar (Overview, War Rooms,
  Integrations, Team, Profile, Settings), org name + owner crown, a PRO TRIAL 14-day
  countdown, the user's avatar + sign-out. Onboarding modal + tour mount here.
  - Overview: stat tiles (live incidents, SEV-1 burning, rooms joined, team members),
    live-now rooms, your recent rooms.
  - War Rooms: declare form (title, severity, role via custom Select, linked GitHub
    repo via searchable Select of the user's repos with private/public badges).
  - Integrations: GitHub card (connect via PAT or OAuth; shows @login when connected),
    Slack card, Jira card (real brand icons).
  - Team: member list with avatars/roles (OWNER/MEMBER/YOU), invite by email or link
    (copy button), pending invites. Personal accounts see a "create organization"
    prompt.
  - Profile: avatar, verified-GitHub badge, default war-room role selector, mini-stats.
  - Settings: PRO TRIAL plan card + trial countdown, preference rows (voice EN-US,
    AI model, notifications, Human gate ALWAYS ON), sign-out.
- **/invite/[token]:** "Join <org> — <inviter> invited you"; accept routes through
  signup/login if needed, then lands on the dashboard with the green "you've been
  added" banner.
- **/incident/[id] (WAR ROOM):** the main screen. Header (severity badge, status
  stepper, live timer, repo chip, approval-waiting pulse, End Session button, Report
  link). Left: StatusPanel (metric tiles with live sparklines, LIVE TELEMETRY badge,
  confidence matrix bars, monitoring readouts), RepoPanel (linked repo, recent commits
  with SUSPECT highlight, merged PRs, failed CI), Participants (avatars, role
  correction, Sentinel with speaking waveform). Center: SentinelBanner (last spoken
  line with the intervention chip), Timeline (iconed rail with filters ALL/SENTINEL/
  EVIDENCE/ACTIONS; Slack/Jira events have brand icons), EvidenceGraph. Right:
  StatePanel (tabs Facts/Hypotheses/Actions/Decisions/Conflicts/Unknowns/Risks with
  confidence rings + evidence), Transcript (colored speaker names, SLACK tag).
  Bottom: VoiceBar (join/mute/leave, agent-audio state chip + autoplay unblock button,
  invite/remove Agora agent, LLM + speed chips, demo controls). ApprovalModal (red,
  blurred backdrop) for critical tools.
- **/incident/[id]/report:** styled markdown report with copy/print.

**useAgoraRoom hook** handles RTC join (with the SERVER-ISSUED uid — joining with a
stale localStorage uid makes Agora silently reject because the token is minted for the
server uid), mic publish with AEC/ANS/AGC (echo cancellation), remote audio playback
with an agent-audio state (`playing`/`none`/`blocked`) + an autoplay-unblock button,
RTM transcript forwarding, and browser STT/TTS fallback. It also detects the
"kicked: same user joined from another tab" case.

**useIncident store** (zustand) is fed by one WebSocket (`/ws/incidents/{id}`); it
holds the incident, transcript, a Sentinel speech queue (for browser TTS when no Agora
agent), and a metric history for sparklines.

---

## 18. THE DEMO REPO: NerdNinzas/demo-payment-service (PayFlow)

A small, believable FastAPI payment service = the "production" target. Public.

**Endpoints:**
- `/` → the public PayFlow status page (light corporate theme; shows deploy SHA,
  outage banner, live success-rate chart, real error logs, an "Attempt a payment"
  button anyone can click). Served by `statuspage.py`.
- `/health` → telemetry: `payment_success_rate` (windowed), `db_connection_utilization`,
  `db_connections_in_use`, `pool_size`, `payments_total`. Sentinel polls this.
- `/logs` → recent log lines (Sentinel reads these as evidence).
- `/pay` → process a payment (grabs a pooled connection, calls the gateway).

**The planted bug (load-triggered):** `payments.py` at HEAD (Prabal's commit) wraps
the gateway charge in a retry loop that **acquires a new DB connection per attempt and
never releases it on a gateway timeout** (~8% of calls). Under sustained load, leaked
connections drain the pool (size 20) until every payment fails with "timeout acquiring
database connection". With NO load, nothing leaks → 100% healthy. This is why an idle
Render instance shows 100% — the bug needs traffic (Sentinel's load generator, or a
manual loop, or the "Attempt a payment" button).

**Git history (authored deliberately for the demo):**
- `d3c0b5d` — **Vijay Singh** — "Initial PayFlow payment service…" (healthy).
- `07d20a0` — **Vijay Singh** — "Add public status page and Render deploy config" →
  tag **v4.1** (last healthy).
- `837c250` — **Prabal Verma** (github login `Prabal-verma`, id 122899996) — "Retry
  gateway timeouts in payment processing to reduce checkout failures" = **THE LEAK** →
  tag **v4.2**, HEAD. Verified on GitHub: this commit's github-login resolves to
  `Prabal-verma` (so claim verification and the narrative both work). Vijay's commits
  show "Vijay Singh" but are "unlinked" (his email isn't verified on a GitHub account —
  irrelevant; only Prabal's commit is verified/reverted).
- Pushed using Prabal's PAT. README is sanitized (does not reveal the bug).

**Reverting HEAD (837c250) returns cleanly to v4.1** because 837c250 only changed
payments.py; the status page + telemetry live in earlier commits and are preserved.

**Render deploy:** `render.yaml` (Python, `pip install -r requirements.txt`,
`uvicorn src.app:app --host 0.0.0.0 --port $PORT`, free plan, autoDeploy on). **NO env
vars needed** — `PORT` and `RENDER_GIT_COMMIT` are auto-provided (the latter drives the
status page's deploy-SHA chip, so the audience sees the SHA change after rollback).
Free tier sleeps after ~15 min idle (~50s cold start); Sentinel's loadgen keeps it
warm during incidents. Current live URL (as of writing):
`https://demo-payment-service.onrender.com/`.

---

## 19. THE FULL DEMO RUNBOOK (step by step, timed)

Pre-flight (once):
1. `cd sentinel && ./start.sh` → backend :8000, frontend :3000, ngrok up.
2. Ensure the demo service is deployed on Render and reachable.
3. Set `MONITOR_URL` in backend/.env to the Render URL (so Sentinel reads REAL
   telemetry and drives load), then restart the backend. (Currently MONITOR_URL may
   still be localhost:9000 — CHECK and update.)
4. Warm the Render service (open the URL) a couple of minutes before, and start load
   so it's already degrading (Option B narrative) — either Sentinel's loadgen (bump
   `LOADGEN_RPS`) or a manual loop:
   `while true; do for i in $(seq 1 40); do curl -s -m5 -X POST https://demo-payment-service.onrender.com/pay -o /dev/null & done; wait; done`
5. Slack #all-sentinel already has a realistic pre-incident standup thread posted as
   Vijay/Prabal/Ankita with their real avatars and natural time gaps.

The run (three screens: war room dark + PayFlow status page light + Slack):
1. **Declare** the SEV-1 on the dashboard, linked to
   `NerdNinzas/demo-payment-service`. Sentinel links the repo (finds Prabal's suspect
   commit `837c250`), snapshots the Jira board, and the war room opens.
2. **Invite Sentinel** (Agora agent) and **Join voice**. Kabir greets the room.
3. **Voice + Slack discussion.** Ankita (SRE) raises the alarm ("pool at 100%,
   payments failing"). Prabal (Backend) notes "I pushed the retry change recently."
   Optionally Prabal and Ankita disagree on DB health → **Sentinel WARNs about the
   conflict**.
4. **Verification moment.** Sentinel verifies Prabal's claim: GitHub shows commit
   `837c250` by Prabal-verma; Jira shows KAN-11 Done → "Verified — and that's exactly
   what correlates with the outage." (Optionally have a third voice claim a fix they
   didn't push → "I couldn't verify that on GitHub.")
5. **Propose → approve.** Sentinel PROPOSES `open_revert_pr` → the red **approval
   modal** → **Vijay approves**.
6. **Real fix.** Sentinel opens + merges a real revert PR (show the GitHub tab). Render
   auto-redeploys (~40–90s — narration window: show the evidence graph, the Slack
   thread, the confidence matrix).
7. **Recovery.** `/health` genuinely recovers; the PayFlow status page flips from red
   "Major outage" to green "All systems operational", the deploy-SHA chip changes, and
   Sentinel announces recovery on voice + Slack.
8. **Report.** Open the report page: impact, findings with evidence, decision ledger,
   actions by owner, tool executions (with the real PR link), unresolved risks, open
   questions, confidence matrix, timeline.

**Rehearsal-tested:** the whole revert→recovery chain works against live Render
(20% success/pool 100% → merge PR → ~36s → 100% success/pool 0%). After a rehearsal,
restore the broken state: force main back to `837c250` and delete the
`sentinel/revert-<sha>` branch (a merged PR record remains — GitHub can't delete PRs;
the real demo just opens the next PR number).

---

## 20. WHAT HAS BEEN VERIFIED WORKING (test evidence)

- Backend unit tests: 4/4 pass — `test_end_to_end_scenario` (scripted PRD run through
  the real pipeline), `test_critical_tool_cannot_auto_execute` (gateway policy),
  `test_claim_verified_when_commit_exists`, `test_claim_flagged_when_no_commit`.
- Live Gemini extraction verified (hypothesis, conflict, action with owner).
- Live Agora agent join + speak verified; full voice conversation held (English +
  Hinglish; "Haan Vijay, mujhe Hindi aur Hinglish dono aati hain").
- Cartesia sonic-3 TTS verified synthesizing real audio; voice heard in the room.
- Slack read+write verified; standup posted as individuals with real avatars; channel
  cleaned (46 msgs deleted).
- Jira live: real ticket created (KAN-4 originally), board cleaned and rebuilt
  (KAN-11..16); assignee status read in verify_claim.
- GitHub: demo repo pushed with correct authorship; suspect detection + claim
  verification fire against the live repo; **real revert PR opened + merged + Render
  recovered** (rehearsal), then restored to broken.
- Mongo: users/orgs/invites/sessions/memberships/incidents persisted; incidents
  rehydrate on restart; org invite accepted across two browser sessions.
- Frontend: all pages screenshot-verified in headless Chrome with zero console errors
  across the redesigns.

---

## 21. KNOWN ISSUES, GOTCHAS, AND MODEL/VERSION CHURN

- **Gemini model churn**: models get deprecated fast. Currently
  `gemini-3.5-flash-lite`. Free tier has tight daily caps (2.5-flash was 20/day). On a
  404, the error names the replacement — update `LLM_MODEL`. Consider a backup key /
  billing for demo day. We skip the LLM on metric-only ticks and fall back to rules on
  failure.
- **Cartesia model churn**: `sonic-2` is sunsetted → use `sonic-3` (Agora docs are
  stale). This was the actual cause of "no TTS audio" for a while.
- **Agora custom-LLM must stream first byte instantly** or replies are voiced-dropped
  (text still reaches the dashboard via our WS). Fixed.
- **Agora managed TTS** is flaky/SKU-limited → we use Cartesia with our own key.
- **Agora join name must be unique** per start (409 otherwise) → timestamped.
- **Client must join RTC/RTM with the server-issued uid** (token mismatch = silent
  rejection). Fixed in useAgoraRoom.
- **Duplicate/echo transcript lines**: the anonymous LLM-callback copy accumulates and
  the mic hears Sentinel's own TTS → dedupe by similarity + drop close matches of
  recent Sentinel lines + mic AEC. Thresholds were tuned so they don't eat real
  speech (an over-aggressive filter was dropping legitimate follow-ups).
- **Slack can't delete other users' messages** with a bot token; "joined the channel"
  notices are un-deletable.
- **Ankita is Slack-only** (no Jira/GitHub); her Jira tickets are tagged in the
  summary but unassigned. Invite needs her email (hidden in Slack).
- **ngrok drops** occasionally; a 404 HTML from the reserved domain = tunnel down.
- **Render free tier** sleeps when idle; the bug needs load to manifest; a fresh
  deploy resets the pool (so both broken and fixed code show 100% with no load — prove
  the fix with load running).
- **Leftover merged PR** after a rehearsal (GitHub can't delete PRs).

---

## 22. HOW TO RUN EVERYTHING LOCALLY

```bash
# Full stack (backend :8000, frontend :3000, ngrok):
cd /Users/vijaysingh/Desktop/agora/sentinel && ./start.sh
# Logs: sentinel/.logs/{backend,frontend,ngrok}.log

# Backend only:
cd sentinel/backend && uv run uvicorn main:app --port 8000
# Tests:
cd sentinel/backend && uv run pytest

# Frontend only:
cd sentinel/frontend && pnpm dev --port 3000

# Demo payment service locally (if not using Render):
cd demo-payment-service && pip install -r requirements.txt
uvicorn src.app:app --port 9000
# (a python venv for it may live in the session scratchpad; recreate with the two lines above)

# Point Sentinel at a monitoring target (local or Render):
# set MONITOR_URL in backend/.env then restart the backend
```

Frontend hot-reloads. Backend must be restarted to pick up `.env` changes (it also
clears the in-process session cache — relevant if you changed a user's onboarded flag
directly in Mongo).

Verify UI changes with headless Chrome via playwright-core (channel:"chrome"); driver
scripts live in `frontend/scripts/*.mjs`; run them from the frontend dir so
`playwright-core` resolves; screenshots go to the session scratchpad. Read the
screenshots to confirm — a blank frame is a failure.

---

## 23. ENVIRONMENT VARIABLE REFERENCE (backend/.env shape)

(Real values are in backend/.env — gitignored. Non-secret identifiers shown.)

```
# Agora
AGORA_APP_ID=5cd07183162c439c902b49ac8cb728de
AGORA_APP_CERTIFICATE=<secret>
AGORA_CUSTOMER_KEY=<secret>
AGORA_CUSTOMER_SECRET=<secret>
AGORA_AGENT_UID=sentinel
AGORA_ASR_VENDOR=ares
AGORA_ASR_LANGUAGE=en-IN,hi-IN
AGORA_TTS_VENDOR=cartesia
AGORA_TTS_API_KEY=<cartesia secret>
AGORA_TTS_PARAMS_JSON={"model_id":"sonic-3","base_url":"wss://api.cartesia.ai","voice":{"mode":"id","id":"cb9c954d-bcaa-43ed-82bf-aeb5e88a3cb5"},"output_format":{"container":"raw","sample_rate":16000},"language":"hi"}

# Public URL (ngrok) for Agora custom-LLM callback + GitHub OAuth callback
PUBLIC_BASE_URL=https://evaluatingly-unparcelling-andree.ngrok-free.dev
SENTINEL_LLM_API_KEY=sentinel-dev-key   # bearer Agora sends us on the custom-LLM call

# LLM (Gemini via OpenAI-compat)
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=<secret>
LLM_MODEL=gemini-3.5-flash-lite

# Integrations
SLACK_BOT_TOKEN=<secret xoxb->
SLACK_CHANNEL=#all-sentinel
JIRA_BASE_URL=https://nerdninzas.atlassian.net
JIRA_EMAIL=rockcodingrookie21@gmail.com
JIRA_API_TOKEN=<secret>
JIRA_PROJECT_KEY=KAN
PAGERDUTY_API_KEY=            # blank → mock
PAGERDUTY_SERVICE_ID=

# GitHub
GITHUB_TOKEN=<Prabal's classic PAT, repo scope — used for revert PRs>
GITHUB_DEFAULT_REPO=NerdNinzas/demo-payment-service
GITHUB_SUSPECT_MINUTES=2880
GITHUB_OAUTH_CLIENT_ID=<secret>
GITHUB_OAUTH_CLIENT_SECRET=<secret>

# Auth & persistence
MONGODB_URL=<secret Atlas URI, db Sentinel>
AUTH_REQUIRED=true
FRONTEND_URL=http://localhost:3000
RESEND_API_KEY=              # blank → mock invites
RESEND_FROM=Sentinel <onboarding@resend.dev>

# Live demo target
MONITOR_URL=                 # set to the Render URL for live telemetry + loadgen
LOADGEN_RPS=2                # bump for a faster break during the demo
DEMO_MODE=true
```

---

## 24. CREDENTIALS INVENTORY (rotate everything after the hackathon)

All live in `backend/.env` (gitignored). Several were pasted into chat during setup —
**rotate after the event**: Agora certificate/customer secret, Gemini key, Cartesia
key, Slack bot token, Jira API token, Prabal's GitHub PAT, GitHub OAuth secret, Mongo
URI. GitHub tokens are also stored in Mongo user docs (plaintext — hackathon scope;
encrypt before any real use). Never commit `.env`. This CONTEXT.md intentionally omits
the secret values.

---

## 25. PENDING / NEXT STEPS / NICE-TO-HAVES

1. **Set MONITOR_URL → the Render URL** and restart, so the outage auto-reproduces and
   Sentinel reads real telemetry (currently may be localhost). Then a full timed dress
   rehearsal.
2. **Push the Sentinel repo** to `NerdNinzas/Sentinel` (user does this).
3. **Resend / PagerDuty** creds → flip those mocks to live (adapters already written).
4. **Invite Ankita to Jira** (need her email) so her SRE tickets can be truly assigned
   and status-checked in verify_claim.
5. **Keyword-aware Jira matching** in verify_claim (currently reports the first
   not-done ticket; could match the ticket most relevant to the claim text).
6. **Scripted incident Slack thread** as Prabal/Ankita during the demo (now possible
   via chat:write.customize) for a teammate who can't be present.
7. Optional Slack **Canvas runbook** + **bookmark** to the status page (needs
   canvases:write / bookmarks:write scopes + reinstall).
8. Discussed-but-not-built: per-incident Slack channels (channels:manage), multi-tenant
   "Add to Slack"/Jira OAuth, a member identity map (email↔github↔slack↔jira ids) on
   profiles, incident replay, postmortem pattern detection across incidents.

---

## 26. WORKING AGREEMENTS (READ THIS)

- **NEVER push to GitHub, and NEVER `git commit`, unless the user explicitly asks.**
  The user commits/pushes themselves. Uncommitted work may exist in the tree. (The
  ONE exception exercised so far: the user explicitly asked to push the
  demo-payment-service repo, which was done with Prabal's token.)
- **backend/.env is gitignored and holds real secrets** — never commit it; remind the
  user to rotate keys after the hackathon.
- **Verify UI changes** with headless Chrome and actually read the screenshots.
- **Dev servers die between sessions** — use `./start.sh` to bring the stack back; the
  demo payment-service venv may need recreating (`pip install -r requirements.txt`).
- **Respect the user's design taste**: noir/orange, readable text, custom dropdowns,
  real brand icons, casual/authentic content (they disliked over-fancy emoji-heavy
  Slack posts and wanted realistic time gaps).
- When a model/vendor errors with "deprecated/sunsetted/no longer available", READ the
  error — it usually names the replacement — and update the config rather than
  guessing.

---

## 27. COMMAND CHEAT-SHEET

```bash
# Start everything
cd /Users/vijaysingh/Desktop/agora/sentinel && ./start.sh

# Health
curl -s localhost:8000/health
curl -s localhost:8000/api/config | python3 -m json.tool   # shows integration flags

# Create an incident via API (test session)
curl -s -X POST localhost:8000/api/incidents \
  -H "authorization: Bearer st_testsession123" \
  -H 'content-type: application/json' \
  -d '{"title":"Payment outage"}'

# Feed a transcript line
curl -s -X POST localhost:8000/api/incidents/<ID>/transcript \
  -H 'content-type: application/json' \
  -d '{"uid":"prabal","text":"I pushed the retry change recently"}'

# Start / stop the Agora agent
curl -s -X POST localhost:8000/api/incidents/<ID>/agent/start
curl -s -X POST localhost:8000/api/incidents/<ID>/agent/stop

# Run the scripted offline demo
curl -s -X POST "localhost:8000/api/incidents/<ID>/demo/start?speed=2&auto_approve=true"

# Live Render status
curl -s https://demo-payment-service.onrender.com/health | python3 -m json.tool

# Manual load to break the deployed service (~90s to drain the pool)
while true; do for i in $(seq 1 40); do curl -s -m5 -X POST https://demo-payment-service.onrender.com/pay -o /dev/null & done; wait; done

# Read the demo repo state on GitHub
curl -s "https://api.github.com/repos/NerdNinzas/demo-payment-service/commits?per_page=3"

# Backend tests
cd sentinel/backend && uv run pytest -q
```

---

*End of CONTEXT.md. Keep it current: when you change an integration, a model version,
a credential location, the demo cast, or the runbook, update the relevant section and
the CLAUDE.md quick-reference.*

---

# APPENDIX A — REST API ENDPOINT REFERENCE

All under the FastAPI app (backend/main.py). Base = `http://localhost:8000`.
Auth = `Authorization: Bearer <session token>` where required (create/join/org/etc).

## Config & incidents (app/api/incidents.py)

- `GET /health` → `{ok:true}`. Liveness.
- `GET /api/config` → integration flags: `{agora_app_id, agora_configured,
  llm_available, llm_model, demo_mode, agent_uid, auth_required, github_oauth,
  mongodb}`. The dashboard reads this to show chips.
- `POST /api/incidents` (auth) body `{title, severity, channel?, repo?}` → creates an
  incident. `repo` defaults to `github_default_repo`; empty string disables linking.
  Kicks off `engine.link_repo` (async) and `engine.link_jira` (async), records
  membership.
- `GET /api/incidents` → list `{id,title,severity,status,started_at,channel,counts}`.
- `GET /api/incidents/{id}` → full incident state (the whole model dumped to JSON).
- `POST /api/incidents/{id}/repo` (auth) body `{repo}` → link/refresh a repo, returns
  `{repo, changes}`.
- `POST /api/incidents/{id}/join` (auth) body `{uid,name,role,focus}` → adds the
  signed-in user as a participant (server overrides uid/name from the account), returns
  `{channel, app_id, uid, tokens:{rtc,rtm}}`. If the agent is in the room it speaks a
  greeting.
- `POST /api/incidents/{id}/participants/{uid}/role` body `{role,focus}` → correct a
  participant's role (role_source=corrected; humans win over inference).
- `POST /api/incidents/{id}/transcript` body `{uid,text,final?,turn_id?}` → ingest a
  transcript line (RTM-forwarded, browser STT, or typed).
- `POST /api/incidents/{id}/proposals/{pid}/decide` body `{approve,by}` → approve or
  reject a critical tool proposal; on approve, Sentinel speaks and the tool executes.
- `POST /api/incidents/{id}/agent/start` → start the Agora agent (502 if Agora join
  fails; 400 if creds missing). Returns Agora's `{agent_id,status,...}`.
- `POST /api/incidents/{id}/agent/stop` → remove the agent from the room.
- `POST /api/incidents/{id}/demo/start?speed=N&auto_approve=bool` → run the scripted
  scenario.
- `POST /api/incidents/{id}/demo/stop` → stop it.
- `POST /api/incidents/{id}/end` (auth) → end the session: stop demo + agent, resolve,
  persist a final snapshot.
- `DELETE /api/incidents/{id}` (auth) → remove a room entirely (store + Mongo).
- `POST /api/incidents/{id}/resolve` → mark resolved.
- `GET /api/incidents/{id}/report` → `{markdown}` final report.
- `GET /api/incidents/{id}/status-speech` → `{text}` spoken status summary.
- `GET /api/tools` → list registered tools `{name,risk,description}`.

## Auth, org, integrations (app/api/auth.py)

- `POST /api/auth/signup` body `{email,password,name}` → `{session,user}`.
- `POST /api/auth/login` body `{email,password}` → `{session,user}`.
- `POST /api/auth/onboard` (auth) body `{account_type, org_name?, org_address?,
  org_website?}` → completes onboarding; creates an org if organization.
- `GET /api/auth/me` (auth) → the public user object.
- `POST /api/auth/notice-ack` (auth) → clear the org_notice banner.
- `POST /api/auth/logout` → `{ok:true}` (client drops the token).
- `GET /api/org` (auth) → `{org, members[], invites[]}`.
- `POST /api/org/invites` (auth) body `{email?}` → `{token, link, emailed,
  mail_configured}`.
- `GET /api/invites/{token}` → `{org_name, invited_by, status, email}`.
- `POST /api/invites/{token}/accept` (auth) → join the org; sets org_notice.
- `POST /api/integrations/github` (auth) body `{token}` → connect a GitHub PAT.
- `DELETE /api/integrations/github` (auth) → disconnect.
- `GET /api/auth/github/login?session=…` → 307 redirect to GitHub OAuth (state =
  session so the callback can attach to the account).
- `GET /api/auth/github/callback?code=…&state=…` → exchanges code, attaches GitHub to
  the account, redirects to the dashboard.
- `GET /api/github/repos` (auth) → the user's repos (for the dropdown).
- `GET /api/me/rooms` (auth) → the user's room memberships (recent rooms).
- `GET /api/integrations` (auth) → status of github/slack/jira/email/mongodb/agora/llm.

## Agora custom-LLM (app/api/agora_llm.py)

- `POST /v1/chat/completions` — the OpenAI-compatible endpoint Agora calls as the
  agent's "LLM". Requires `Authorization: Bearer <SENTINEL_LLM_API_KEY>`. Resolves the
  incident by `channel` (in the body) or the latest live one. STREAMS the first SSE
  byte immediately, runs `engine.tick` inside the stream (12s cap), and streams back
  Sentinel's utterance (or empty for WAIT). Returns `text/event-stream` with
  `chat.completion.chunk` events + `data: [DONE]`.

## WebSocket (app/api/ws.py)

- `WS /ws/incidents/{id}` — on connect sends the full state + a transcript bulk, then
  streams events. Message types (see Appendix D).

---

# APPENDIX B — KEY FUNCTIONS PER MODULE

## app/core/config.py
- `Settings` (pydantic-settings) — all env-backed config. `get_settings()` cached.

## app/core/agora.py :: AgoraConvoAI
- `configured` — true if app_id + customer key/secret present.
- `build_join_body(channel, token, system_prompt, greeting, name)` — assembles the
  full join payload (asr/llm-custom/tts blocks).
- `join(body)` / `leave(agent_id)` / `speak(agent_id, text, priority, interruptable)` /
  `interrupt(agent_id)` / `query(agent_id)`.

## app/core/token.py
- `build_tokens(channel, uid, expire)` → `{rtc, rtm}` AccessToken2 tokens (empty when
  no certificate — Agora testing mode).

## app/core/db.py
- `connect()` / `available()` — Mongo lifecycle.
- `upsert_user`, `create_session`, `get_session_user`, `delete_session`.
- `record_membership`, `user_rooms`.
- `mark_dirty(incident_id)` (write-behind, 2s flush), `save_incident_now(inc)`,
  `load_incidents(limit)` (rehydration).

## app/core/accounts.py
- `hash_password` / `verify_password` (pbkdf2).
- `signup`, `login`, `onboard`, `org_overview`, `create_invite`, `invite_info`,
  `accept_invite`, `ack_notice`, `public_user`.

## app/core/auth.py
- `github_user(token)`, `login_with_token`, `oauth_exchange(code)`, `resolve(header)`,
  `current_user` / `require_user` (FastAPI deps), `_cache` (shared session cache).

## app/engine/store.py :: IncidentStore
- `create`, `get`, `by_channel`.
- `subscribe/unsubscribe/broadcast/publish_state` (WebSocket bus; publish_state bumps
  version and marks Mongo dirty).
- `add_participant`, `add_transcript`, `sentinel_said`, `set_metrics`.
- `apply_ops(inc, ops)` → the op applier; `_apply` handles every op type with
  de-duplication and timeline events.

## app/engine/extractor.py
- `RuleExtractor.extract(inc, lines)` — regex/keyword extraction → `{ops, intervention}`.
- `llm_extract(inc, lines, events)` — LLM path (JSON).
- `_digest(inc)` — the compact state sent to the model.

## app/engine/engine.py :: Engine (the orchestrator)
- `start/stop` — starts follow-up loop, slack loop, live-monitor loop, loadgen loop.
- `ingest_transcript(inc, uid, text, ...)` — dedupe/echo-suppress, add line, schedule
  a tick.
- `tick(inc)` — the core: extractor → apply ops → state rules → repo evidence rules →
  confidence → intervention (returns speech or None).
- `say(inc, text, action, urgency)` — record + speak (Agora speak, and Slack echo when
  applicable).
- `_metric_rules`, `_state_rules`, `_repo_evidence_rules` — deterministic rules.
- `_followup_loop` / `_followup_for` — chase stale/unowned actions, pending approvals.
- `_slack_loop` — poll Slack channel, ingest human messages, timeline events.
- `_live_monitor_loop` — poll `{MONITOR_URL}/health` + `/logs` into the pipeline.
- `_loadgen_loop` — drive `{MONITOR_URL}/pay` (ramps during live incidents).
- `verify_claim(inc, uid, claim_text)` — GitHub + Jira cross-check (see §14).
- `link_repo(inc, repo, token)` / `link_jira(inc)` — snapshot repo/Jira into timeline.
- `start_agent(inc, token)` / `stop_agent(inc)` — Agora agent lifecycle (3× retry).
- `run_scenario/_scenario` — the scripted demo.

## app/tools/gateway.py
- `register(name, risk, description)` decorator; `REGISTRY`.
- `propose(inc, tool, args, reason)` → safe auto-run / critical pending.
- `decide(inc, proposal_id, approve, by)` → approve/reject + execute.
- `execute(inc, prop, approved_by)` → policy re-check + adapter call + timeline.

## app/tools/adapters.py
- `Slack`: `post`, `history(oldest)`, `user_name(uid)`, `channel_id()`.
- `Jira`: `create`, `open_issues`, `issues_for(person)`, `configured`.
- `PagerDuty.page`, `Deploy.rollback/restart/failover/scale/disable_flag` (mock).

## app/tools/github.py
- `fetch_changes(repo, incident_start, token)` — evidence window.
- `create_issue`, `comment_on_pr`, `open_revert_pr(repo, sha, reason)` (real).

## app/engine/confidence.py
- `compute(inc)` → ConfidenceMatrix; `spoken_summary(inc)`.

## app/engine/report.py
- `generate(inc)` → markdown report (LLM prose + deterministic fallback).
- `status_speech(inc)` → the spoken status summary.

---

# APPENDIX C — THE SCRIPTED SCENARIO (app/mock/scenario.py)

`POST /api/incidents/{id}/demo/start` replays the PRD payment-outage through the REAL
pipeline (works fully offline with the rule extractor). Participants: Arjun (IC),
Rahul (backend), Ananya (SRE), Priya (support). Steps (abridged): monitoring detects
payment success 98.7% → 21% (SEV-1); support reports customers can't pay; Rahul
hypothesizes DB overload; Arjun assigns checks; Ananya says DB looks healthy (→
conflict); monitoring shows DB 100% (→ Sentinel asks to verify); team confirms pool
exhaustion (hypothesis → confirmed); deployment v4.2 identified; rollback proposed;
`await_approval` blocks until a human approves; recovery detected; Sentinel:
"Payment success has recovered… however root cause remains unconfirmed." This scenario
predates the live-Render flow and is the safe offline fallback for the demo.

---

# APPENDIX D — WEBSOCKET MESSAGE TYPES (frontend store consumes these)

- `{type:"state", incident}` — full snapshot (the store swaps it in).
- `{type:"event", event}` — a new timeline event.
- `{type:"transcript", line}` / `{type:"transcript_bulk", lines}` — transcript.
- `{type:"sentinel", text, action}` — Sentinel spoke (queued for browser TTS when no
  Agora agent).
- `{type:"metrics", metrics}` — new monitoring snapshot (feeds sparklines).
- `{type:"approval_required", proposal}` — show the approval modal.

Timeline-kind → icon (frontend Timeline.tsx): incident=Siren(red), metric=BarChart
(cyan), hypothesis=Lightbulb(amber), fact=CheckCircle(green), action=ListTodo(blue),
decision=Gavel(purple), conflict=AlertTriangle(amber), unknown=HelpCircle(muted),
risk=Flame(red), approval=ShieldAlert(red), tool=Wrench(cyan), sentinel=Bot(blue),
participant=UserPlus(green), slack=MessageSquare(#E01E5A), jira=KanbanSquare(#2684FF).

---

# APPENDIX E — SUGGESTED DEMO DIALOGUE

These are example lines that make each Sentinel feature fire. Voice or Slack both work
(both feed the same pipeline). Keep them casual and natural.

Pre-incident (already staged in Slack as a standup thread):
- Prabal: "pushed the gateway retry fix last night, should stop those random checkout
  timeouts"
- Ankita: "dashboards look fine, success rate steady around 99"
- Vijay: "nice work, how's the latency ticket?"

Incident (live, in the war room / Slack):
- Ankita (SRE): "monitoring's lighting up — payment success is tanking and the DB
  connection pool is pinned at 100%." → customer-impact fact + confirms pool-exhaustion
  hypothesis.
- Prabal (Backend): "the app side looks fine to me though, queries return." → **conflict
  with Ankita** → Sentinel WARNs and asks to verify.
- (telemetry confirms Ankita) Sentinel: "monitoring shows the pool at 100% — that
  supports pool exhaustion."
- Prabal: "I pushed the retry logic change to payment-api recently." → Sentinel
  verifies: "Verified — I can see Prabal-verma's commit 837c250, and Jira KAN-11 is
  Done. That retry change correlates with the pool exhaustion."
- Prabal: "let's revert it." → Sentinel PROPOSES `open_revert_pr` → **approval modal**.
- Vijay (IC): clicks Approve → Sentinel opens + merges the revert PR → Render
  redeploys.
- Ankita: "payments are succeeding again, the status page is green, connections back to
  normal." → recovery evidence.
- Sentinel: "Payment success has recovered. The incident appears resolved. Root cause:
  the v4.2 retry change leaked DB connections; reverted via PR. Follow-ups filed."

Optional "catch a bluff" beat: a third person claims "I deployed the config fix" with
no matching commit → Sentinel: "I couldn't verify that on GitHub — is it on another
branch or still local?"

---

*Appendix end. This document plus CLAUDE.md should be enough for a fresh Claude to
pick up the project cold.*
