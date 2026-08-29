# Sentinel — AI Incident Commander

> The missing intelligence layer inside the incident room. Sentinel joins the Agora voice room like another teammate,
> turns the conversation into a live, evidence-backed incident state (facts ≠ hypotheses), tracks who owns what,
> flags contradictions and unknowns, speaks only when it helps — and never runs a production action without a human.

Built for **EchoSphere: Agora Conversational AI Hackathon** (problem statement: *Voice AI Incident Commander*).

## Repo layout

```
sentinel/
├── backend/            FastAPI (Python 3.12, uv)
│   ├── main.py         app wiring
│   └── app/
│       ├── core/       config, Agora ConvoAI REST client, AccessToken2 (RTC/RTM tokens)
│       ├── engine/     models · store/event-bus · extractor (LLM + rules) · engine · confidence · report
│       ├── tools/      tool gateway (safe vs critical, human approval) + Slack/Jira/PagerDuty/deploy adapters
│       ├── mock/       mock monitoring + scripted payment-outage scenario
│       ├── llm/        OpenAI-compatible client + prompts
│       └── api/        REST · WebSocket · /v1/chat/completions (Agora custom LLM)
├── frontend/           Next.js 16 war-room dashboard (Agora RTC + RTM, zustand, framer-motion)
└── docs/               ROADMAP.md · AGORA.md
```

## Run it (2 terminals)

```bash
# backend
cd backend && cp .env.example .env   # fill AGORA_* / LLM_* when you have them; blank = offline demo
uv sync && uv run uvicorn main:app --reload --port 8000

# frontend
cd frontend && pnpm install && pnpm dev     # http://localhost:3000
```

Open http://localhost:3000 → enter your name/role → **Declare** → click **▶ Run payment-outage demo**.
With no keys at all, the rule-based extractor + browser TTS run the full story; add `LLM_API_KEY` for LLM extraction and
`AGORA_*` + `PUBLIC_BASE_URL` (ngrok) to put Sentinel in the real voice room. See `docs/AGORA.md`.

```bash
cd backend && uv run pytest      # end-to-end scenario test: conflict → approval → rollback → recovery → report
```

## How Sentinel thinks

| Bucket | Meaning | How it gets there |
|---|---|---|
| **Fact** | evidence-backed | monitoring/tool data, or a hypothesis confirmed by data **and** the team |
| **Observation** | someone said it | participant claim without data |
| **Hypothesis** | belief | "I think / probably / suspect…" — never promoted by the AI's own certainty |
| **Action** | task + owner | "Rahul, check X" / "I'll check X" / "someone check X" (unowned → Sentinel chases) |
| **Decision** | immutable ledger | commander agreement, approvals |
| **Conflict** | two claims disagree | polarity clash on the same topic between two people |
| **Unknown** | needed, missing | blast radius, change correlation, action safety… |
| **Risk** | future problem | root cause unproven, config review, etc. |

Intervention engine decides `WAIT / ASK / WARN / SUMMARIZE / CLARIFY / PROPOSE`; critical tools
(`rollback_deployment`, `restart_service`, `failover_database`, `scale_service`, `disable_feature_flag`) are blocked at the
gateway until a human approves on the dashboard; safe tools (Slack, Jira, PagerDuty page, monitoring queries) auto-run.
The **Confidence Matrix** is computed from state, never asserted by the LLM.

## Architecture

```
Browser (Next.js)  ──RTC audio──▶  Agora channel  ◀──RTC audio──  Sentinel agent (Agora ConvoAI: ASR → LLM → TTS)
      │  ▲                                                                    │
      │  └── RTM: user.transcription {user_id, text, final} ─────────────────┘
      │  (forwarded to backend => speaker-attributed transcript)
      ▼
FastAPI backend  ◀── /v1/chat/completions (Agora calls us as the agent's "custom LLM")
   ├─ Engine: extractor (LLM|rules) → state ops → store → WebSocket fan-out
   ├─ Deterministic rules: metrics→facts, unknowns, recovery, follow-ups
   ├─ Tool Gateway: policy → approval → adapter → audit
   └─ speak REST → agent TTS for proactive interventions (follow-ups, alerts)
```
