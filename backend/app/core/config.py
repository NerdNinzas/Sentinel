from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---- Agora -------------------------------------------------------
    agora_app_id: str = ""
    agora_app_certificate: str = ""          # for RTC/RTM token generation
    agora_customer_key: str = ""             # REST basic-auth (console -> RESTful API)
    agora_customer_secret: str = ""
    agora_agent_uid: str = "sentinel"        # string uid for the AI participant
    agora_asr_vendor: str = "ares"           # ares | deepgram | microsoft ...
    agora_asr_language: str = "en-US"
    agora_tts_vendor: str = "openai"         # openai | elevenlabs | minimax ...
    agora_tts_params_json: str = '{"model":"gpt-4o-mini-tts","voice":"alloy"}'
    agora_tts_api_key: str = ""

    # ---- Public URL of this backend (Agora must reach /v1/chat/completions)
    public_base_url: str = "http://localhost:8000"
    sentinel_llm_api_key: str = "sentinel-dev-key"   # Agora -> us auth

    # ---- LLM (OpenAI-compatible; works for OpenAI, Gemini compat, Groq...)
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    # ---- Integrations (optional; mock adapters used when blank)
    slack_bot_token: str = ""
    slack_channel: str = "#incidents"
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "INC"
    pagerduty_api_key: str = ""
    pagerduty_service_id: str = ""

    github_token: str = ""
    github_default_repo: str = "NerdNinzas/demo-payment-service"
    github_suspect_minutes: int = 2880   # a change within this window before the incident is "suspect" (demo-friendly)

    mongodb_url: str = ""
    auth_required: bool = True
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""
    frontend_url: str = "http://localhost:3000"
    resend_api_key: str = ""
    resend_from: str = "Sentinel <onboarding@resend.dev>"

    database_url: str = "sqlite+aiosqlite:///./sentinel.db"
    demo_mode: bool = True
    monitor_url: str = ""            # deployed demo service; enables live telemetry + load generator
    loadgen_rps: float = 2.0
    report_timezone: str = "Asia/Kolkata"


@lru_cache
def get_settings() -> Settings:
    return Settings()
