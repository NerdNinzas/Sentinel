# Agora integration notes

## What we use
- **Agora RTC (Web SDK `agora-rtc-sdk-ng`)** — humans join the voice channel from the dashboard.
- **Agora Conversational AI Engine (REST v2)** — Sentinel joins the same channel as an agent:
  `POST https://api.agora.io/api/conversational-ai-agent/v2/projects/{appid}/join` (Basic auth = customer key:secret).
  We set `llm.vendor = "custom"` and point `llm.url` at our backend's `/v1/chat/completions`, so Agora does
  ASR + TTS + turn-taking and **our engine is the brain**.
- **Agora RTM (`agora-rtm`)** — with `advanced_features.enable_rtm=true` + `parameters.data_channel="rtm"` the agent publishes
  `user.transcription` / `assistant.transcription` JSON messages (`user_id`, `turn_id`, `text`, `final`). The dashboard
  forwards final user lines to `POST /api/incidents/{id}/transcript` → speaker-attributed transcript.
- **`/agents/{id}/speak`** — proactive speech (follow-ups, monitoring alerts): `{text, priority: INTERRUPT|APPEND|IGNORE, interruptable}`.

## Custom LLM contract (what Agora sends us)
OpenAI chat-completions shape, `stream: true` required. Response = SSE chunks (`chat.completion.chunk`) + `data: [DONE]`.
Optional first chunk `chat.completion.custom_metadata` (we send `interruptable: true`).
Extra fields with `vendor=custom`: `turn_id`, `timestamp`, per-message `metadata`. The speaker uid is **not** in the LLM request,
which is why we rely on the RTM transcript stream for attribution (with dedupe on the backend).

## Console checklist (console.agora.io)
1. Project → copy **App ID**; enable **App Certificate** (or keep testing mode → empty tokens).
2. Enable **Conversational AI Engine** on the project.
3. Developer Toolkit → **RESTful API** → create Customer ID / Secret → `AGORA_CUSTOMER_KEY/SECRET`.
4. Choose ASR (`ares` built-in) and a TTS vendor (OpenAI/ElevenLabs/MiniMax…) + key.
5. Backend must be reachable from Agora: `ngrok http 8000` → `PUBLIC_BASE_URL`.

## Known open questions
- `remote_rtc_uids: ["*"]` (subscribe to everyone) is documented on the join page but the API reference says single uid — verify on the account.
- Empty LLM response = agent stays silent (intended). If the engine treats it as failure and plays `failure_message`, switch to returning a single space.
