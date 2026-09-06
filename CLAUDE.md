# CLAUDE.md — Sentinel project context

> For the FULL detailed context, read **CONTEXT.md** in this folder (comprehensive: architecture, every integration with credentials/gotchas, the demo cast, the demo runbook, known issues). This file is the short quick-reference.

> Read this first. It is the full state of the project so any Claude instance (or human)
> can continue without archaeology. Keep it updated when you change architecture,
> integrations, or flows.

## What this is

**Sentinel — AI Incident Commander**, built by **NerdNinzas** for the EchoSphere hackathon
(Agora Conversational AI track, problem statement: "Voice AI Incident Commander").
A real-time AI teammate that joins an incident war room (voice + Slack + dashboard),
separates **facts from hypotheses**, tracks **actions with owners**, detects **conflicts**,
verifies claims against **GitHub**, and **never executes production actions without human
approval**. Final pitch line: *"the missing intelligence layer inside the incident room."*

## Repo layout

```
agora/
├── sentinel/                  ← main repo (git; remote: https://github.com/NerdNinzas/Sentinel.git — NOT pushed yet, user pushes)
│   ├── backend/               FastAPI, Python 3.12, uv. Entry: main.py
│   │   └── app/
│   │       ├── core/          config.py (pydantic-settings, .env) · agora.py (ConvoAI REST client)
│   │       │                  token.py + access_token2.py/Packer.py (vendored Agora AccessToken2 '007')
│   │       │                  db.py (Mongo/motor) · auth.py (sessions) · accounts.py (email/pass + orgs + invites)
│   │       │                  mailer.py (Resend)
│   │       ├── engine/        models.py (state model) · store.py (in-memory store + WS bus + op applier)
│   │       │                  extractor.py (Gemini + regex rule extractor) · engine.py (orchestrator)
│   │       │                  confidence.py · report.py
│   │       ├── tools/         gateway.py (safe/critical tool registry + human approval)
│   │       │                  adapters.py (Slack r/w, Jira, PagerDuty, mock Deploy) · github.py (evidence + real revert PR)
│   │       ├── llm/           client.py (OpenAI-compatible; Gemini via compat endpoint) · prompts.py
│   │       ├── mock/          monitoring.py (mock + live ingest) · scenario.py (scripted PRD demo)
│   │       └── api/           incidents.py · auth.py · agora_llm.py (/v1/chat/completions) · ws.py
│   ├── frontend/              Next.js 16, Tailwind v4, noir/orange editorial theme (Anton + IBM Plex Mono + Inter)
│   │   └── src/
│   │       ├── app/           / (landing) · /login · /dashboard (sidebar console) · /invite/[token]
│   │       │                  /incident/[id] (war room) · /incident/[id]/report
│   │       ├── components/    war-room panels, Select (custom dropdown), onboarding.tsx (modal+tour), ui.tsx (icons/avatars)
│   │       ├── hooks/useAgoraRoom.ts   RTC join + RTM transcript forward + browser STT/TTS fallback
│   │       ├── store/useIncident.ts    zustand fed by one WebSocket
│   │       └── lib/api.ts     session-bearer fetch client
│   ├── start.sh               boots backend :8000 + frontend :3000 + ngrok (logs in .logs/)
│   └── docs/                  ARCHITECTURE.md (deep dive) · AGORA.md · ROADMAP.md
└── demo-payment-service/      separate repo (push as NerdNinzas/demo-payment-service). FastAPI payment API
                               with PLANTED BUG: HEAD commit (tag v4.2) leaks a DB connection per gateway
                               timeout in the retry loop → pool drains under load → payments fail.
                               render.yaml for Render auto-deploy. /health /logs /pay endpoints.
```

## The core state model (backend/app/engine/models.py)

Everything extracted lands in one bucket of `Incident`: Fact (evidence-backed), Observation,
Hypothesis (unverified→investigating→confirmed/rejected; confirmed needs monitoring evidence
AND human agreement), Decision (immutable ledger), Action (owner, chased when stale),
Conflict, Unknown, Risk, TimelineEvent, ToolProposal, ConfidenceMatrix (computed in
confidence.py — never asserted by the LLM). Store mutations go through `store.apply_ops`
(typed ops emitted by the extractor) — never free-form state rewrites.

## How a sentence flows

Voice: mic → Agora RTC → Agora agent (ares ASR, turn detection) → (a) RTM
`user.transcription {user_id,text,final}` → dashboard forwards to POST /transcript (speaker
attribution) and (b) Agora calls our `/v1/chat/completions` as its "custom LLM" (`llm.vendor:
custom`, url = PUBLIC_BASE_URL via ngrok) = "turn ended, you may reply". Engine tick:
pending lines + monitoring events → extractor (Gemini `LLM_API_KEY` set → llm_extract; else/on
failure → RuleExtractor regexes) → ops → store → WS broadcast → deterministic rules
(metrics→facts, unknowns, recovery, repo evidence) → intervention decision
(WAIT/ASK/WARN/SUMMARIZE/CLARIFY/PROPOSE, 8s throttle) → SSE back to Agora (empty = silence)
or `speak` REST for proactive lines (follow-up loop chases stale/unowned actions, pending
approvals). Slack: `_slack_loop` polls the org channel every 4s during live incidents; human
messages → same pipeline; Sentinel's utterances echo back to Slack (🤖 prefix) when Slack
participants are active. No Agora creds → browser SpeechRecognition/speechSynthesis fallback;
no LLM key → rule extractor: the demo always works offline.

## Key engine behaviors (all tested)

- Conflict detection: per-topic polarity claims; opposite claim by a different person → one
  conflict + WARN asking for verification (never picks a side).
- Claim verification (`engine.verify_claim`): "I pushed/deployed/completed…" → fetch linked
  repo commits (committer date = push time), match author (github_login from user doc, else
  first-name) within 90 min → ✅ Verified fact + action annotated + spoken/Slack confirmation;
  no match → ⚠ "Unverified claim" risk + polite public callout.
- GitHub evidence: incident creation fetches linked repo's 24h window (commits/PRs/failed CI);
  changes ≤90 min before incident are `suspect`; causal hypotheses auto-receive the top
  suspect commit as evidence; "what changed?" unknowns auto-answered.
- Tool gateway: safe (slack post, jira ticket, github issue/comment, monitoring query,
  page_oncall) auto-run; critical (open_revert_pr, rollback_deployment, restart, failover,
  scale, flag) BLOCKED until a human approves in the UI modal; policy re-checked at execution
  (test asserts critical can never auto-run). Approval writes a Decision ledger entry.
- `open_revert_pr` is REAL when any stored user has a repo-scope GitHub token: creates revert
  commit (parent tree) on branch `sentinel/revert-<sha>`, opens PR, merges it → Render
  auto-deploys → live recovery.
- Live telemetry: `MONITOR_URL` set → poll `{url}/health` + `/logs` every 5s into the metrics
  pipeline + a load generator hits `{url}/pay` (LOADGEN_RPS while incident live, 0.2 idle
  keep-warm). Guard: skipped while a scripted demo scenario runs.
- Scripted demo: `POST /incidents/{id}/demo/start?speed=N` replays the PRD payment-outage
  through the real pipeline (works fully offline).

## Auth, orgs, persistence

- Email/password signup+login (`accounts.py`, pbkdf2). Sessions = bearer `st_…` tokens
  (Mongo `sessions` + process cache). AUTH_REQUIRED=true gates create/join.
- Onboarding modal on first dashboard visit: personal vs organization (name/address/website
  → `orgs` collection, creator = owner). Guided 5-step tour after (localStorage flags).
- Invites: `POST /org/invites {email?}` → token + link `/invite/<token>`; email sent via
  Resend when RESEND_API_KEY set (mailer.py; graceful mock otherwise). Accept → member joins
  org, gets `org_notice` banner ("You have been added to X"). Members see each other in Team.
- GitHub is an INTEGRATION now (not auth): per-user PAT paste or OAuth
  (`/api/auth/github/login?session=…` attaches to the signed-in account). User's token powers
  private-repo evidence, repo dropdown, revert PRs.
- MongoDB (Atlas, `Sentinel` db): users, orgs, invites, sessions, memberships,
  incidents (full state snapshots, write-behind 2s, REHYDRATED on startup — rooms survive
  restarts). Mongo down → memory-only, everything still works.

## Integrations status

- **Agora** ✅ live: app id/cert/customer key+secret in backend/.env. Managed TTS
  (openai tts-1, credential_mode=managed — note: their API wants `params.url`, docs lie about
  `base_url`; only openai+minimax allowed managed on free SKU; occasional transient 500
  "model service temporarily unavailable" → join retries 3x). ares ASR. `remote_rtc_uids:["*"]`.
- **Gemini** ✅ live: gemini-2.5-flash via OpenAI-compat endpoint (LLM_BASE_URL/LLM_API_KEY).
- **ngrok** ✅: reserved domain evaluatingly-unparcelling-andree.ngrok-free.dev = PUBLIC_BASE_URL
  (Agora custom-LLM callback + GitHub OAuth callback). Must be running for live voice/OAuth.
- **Slack** ✅ live: workspace "sentinel" (user may rename to NerdNinzas — safe), bot token in
  .env, channel #all-sentinel, scopes chat:write channels:read channels:history users:read.
  Read+write loop working. Org-level (one workspace per deployment); multi-tenant "Add to
  Slack" OAuth is a known future upgrade.
- **Jira / PagerDuty** ⏳ adapters ready, run as mocks until JIRA_*/PAGERDUTY_* creds set.
- **Resend** ⏳ mailer ready, mock until RESEND_API_KEY set.
- **GitHub OAuth app** ✅ configured (client id/secret in .env, callback = ngrok).

## Running

```bash
cd sentinel && ./start.sh     # backend :8000, frontend :3000, ngrok; logs in .logs/
cd backend && uv run pytest   # 4 tests: e2e scenario, gateway policy, claim verify ×2
```
Local demo service: `uvicorn src.app:app --port 9000` in demo-payment-service
(MONITOR_URL=http://localhost:9000 currently in backend/.env — switch to the Render URL
after the user deploys).

## IMPORTANT working agreements

- **NEVER push to GitHub. NEVER `git commit` unless the user explicitly asks** — the user
  commits/pushes themself (remote `origin` is set). Uncommitted work may exist in the tree.
- backend/.env is gitignored and holds real secrets (Agora, Gemini, Slack, Mongo, GitHub
  OAuth). Never commit it; user should rotate keys after the hackathon (several were pasted
  in chat).
- Verify UI changes with headless Chrome (playwright-core, channel:"chrome"); driver scripts
  live in frontend/scripts/*.mjs; screenshots to the session scratchpad.
- The user (Vijay / NerdNinzas, aatif.pmb@gmail.com) prefers: noir/orange editorial UI
  (split-flap hero, mono labels, numbered sections), readable text (not too dim), custom
  dropdowns (no native selects), real brand icons.

## Demo repo — LIVE STATE (NerdNinzas/demo-payment-service, PUSHED)

Pushed to GitHub with authored history:
- `d3c0b5d` **Vijay Singh** — Initial PayFlow service (healthy)
- `07d20a0` **Vijay Singh** — status page + Render config → tag **v4.1** (last healthy)
- `837c250` **Prabal Verma** (github login `Prabal-verma`, id 122899996) — "Retry gateway timeouts…"
  = THE LEAK → tag **v4.2**, HEAD. Reverting HEAD returns cleanly to v4.1.
Prabal's token (ghp_ptLVDR…, repo scope) was used to push. Demo narrative: Prabal says
"I pushed this recently" → Sentinel flags 837c250 as suspect, verifies it's Prabal-verma's
commit, WARNs, proposes revert → Vijay approves → real revert PR merged → Render redeploys → recovery.
Sentinel config: github_default_repo=NerdNinzas/demo-payment-service; github_suspect_minutes=2880
(generous window so the commit stays "suspect"/verifiable even hours later). Verified live:
suspect detection + Jira status check + "Verified — I can see Prabal-verma's commit 837c250" all fire.
Service has a public status page at `/` (PayFlow, light theme, shows deploy SHA, outage banner,
live success-rate chart, real error logs, "Attempt a payment" button). Render needs NO env vars
(PORT + RENDER_GIT_COMMIT auto-provided). AFTER user deploys → set MONITOR_URL to the onrender URL.

## Pending / next steps

1. User deploys demo-payment-service to Render → set MONITOR_URL to the Render URL.
2. User pushes both repos to GitHub (sentinel → NerdNinzas/Sentinel).
3. Jira + PagerDuty + Resend creds → flip mocks to live (adapters already written).
4. Nice-to-haves discussed: per-incident Slack channels (channels:manage), multi-tenant
   "Add to Slack"/Jira OAuth, member identity map (email↔github↔slack↔jira ids) on profiles,
   incident replay, postmortem pattern detection.
5. Demo runbook lives at the bottom of docs/ROADMAP.md + in chat: declare linked incident →
   loadgen degrades real service → voice+Slack discussion → conflict WARN → suspect commit →
   human approves revert → real PR merged → Render redeploys → real recovery → report.
