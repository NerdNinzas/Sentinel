# Roadmap

## Phase 0 — Foundations ✅ (done)
- Repo, backend (FastAPI/uv), frontend (Next.js 16 + Tailwind 4), Agora REST client, AccessToken2 tokens
- Incident state model (Fact/Observation/Hypothesis/Decision/Action/Conflict/Unknown/Risk/Timeline/Approval/ToolExecution)
- Store + WebSocket event bus; rule-based + LLM extractors; confidence matrix; report generator
- Tool gateway with safe/critical policy + human approval; Slack/Jira/PagerDuty/deploy adapters (real when configured, mock otherwise)
- Mock monitoring + scripted PRD scenario; end-to-end pytest
- War-room dashboard: header, status/confidence, participants (role correction), timeline, state tabs, transcript, approval modal, evidence graph, voice bar, report page

## Phase 1 — Live voice with Agora (next)
1. Create project in console.agora.io → App ID + certificate; enable **Conversational AI Engine**; create RESTful API customer key/secret
2. Expose backend with ngrok/cloudflared → `PUBLIC_BASE_URL`; pick TTS vendor + key (`AGORA_TTS_*`)
3. Click **Invite Sentinel** → verify: greeting spoken, `user.transcription` arrives over RTM, backend attributes speakers, agent replies via `/v1/chat/completions`
4. Verify `remote_rtc_uids: ["*"]` works on the account (docs disagree: one page says wildcard, API ref says single uid). Fallback: run one agent per speaker uid with `speak` for output, or Agora Real-Time STT for multi-speaker transcripts
5. Tune turn-taking (`turn_detection`, `interruptable`) so Sentinel doesn't talk over the room

## Phase 2 — Intelligence quality
- LLM extraction eval against the scripted scenario (target: 90% of obvious facts/actions/hypotheses)
- Better conflict topic modelling (embedding similarity instead of keyword topics)
- Follow-up tuning: overdue actions, unowned actions, pending approvals
- Persist incidents (SQLite/Postgres) + pgvector for similar-incident retrieval

## Phase 3 — Demo polish
- Incident replay (scrub the timeline; state reconstructed per event)
- Post-incident pattern detection ("3rd DB-pool incident in 30 days")
- Slack live channel + Jira board on screen during demo
- PPT storyline (12 slides) with the demo as the centrepiece

## Stretch
- PagerDuty-triggered incident creation (webhook → auto-create room + invite Sentinel)
- Multilingual rooms (Agora ASR language per speaker)
- Real Prometheus/Datadog adapter behind the same `query()` / `recent_deployments()` interface
