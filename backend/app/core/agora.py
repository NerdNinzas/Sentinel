"""Thin client for the Agora Conversational AI Engine REST API (v2).

Docs: https://docs.agora.io/en/conversational-ai/rest-api/join
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings

log = logging.getLogger("sentinel.agora")
BASE = "https://api.agora.io/api/conversational-ai-agent/v2/projects"


class AgoraConvoAI:
    def __init__(self) -> None:
        s = get_settings()
        self.app_id = s.agora_app_id
        cred = f"{s.agora_customer_key}:{s.agora_customer_secret}".encode()
        self._headers = {
            "Authorization": "Basic " + base64.b64encode(cred).decode(),
            "Content-Type": "application/json",
        }
        self._http = httpx.AsyncClient(timeout=30)

    @property
    def configured(self) -> bool:
        s = get_settings()
        return bool(s.agora_app_id and s.agora_customer_key and s.agora_customer_secret)

    # ------------------------------------------------------------------
    def build_join_body(self, channel: str, token: str, system_prompt: str,
                        greeting: str, name: str) -> dict[str, Any]:
        s = get_settings()
        tts_params = json.loads(s.agora_tts_params_json)
        if s.agora_tts_api_key:
            tts_params["api_key"] = s.agora_tts_api_key
        return {
            "name": name,
            "properties": {
                "channel": channel,
                "token": token,
                "agent_rtc_uid": s.agora_agent_uid,
                "enable_string_uid": True,
                # "*" subscribes to every human in the war room.
                "remote_rtc_uids": ["*"],
                "idle_timeout": 600,
                "advanced_features": {"enable_rtm": True},
                "parameters": {
                    "data_channel": "rtm",
                    "enable_metrics": True,
                    "enable_error_message": True,
                },
                "asr": {
                    "vendor": s.agora_asr_vendor,
                    "language": s.agora_asr_language,
                },
                "llm": {
                    "vendor": "custom",
                    "style": "openai",
                    "url": f"{s.public_base_url}/v1/chat/completions",
                    "api_key": s.sentinel_llm_api_key,
                    "system_messages": [{"role": "system", "content": system_prompt}],
                    "greeting_message": greeting,
                    "failure_message": "Sentinel is temporarily unable to respond.",
                    "max_history": 32,
                    "params": {"model": "sentinel-v1", "channel": channel},
                },
                "tts": {"vendor": s.agora_tts_vendor, "params": tts_params},
            },
        }

    async def join(self, body: dict[str, Any]) -> dict[str, Any]:
        r = await self._http.post(f"{BASE}/{self.app_id}/join", headers=self._headers, json=body)
        if r.status_code >= 400:
            log.error("agora join failed %s %s", r.status_code, r.text)
            r.raise_for_status()
        return r.json()

    async def leave(self, agent_id: str) -> None:
        await self._http.post(f"{BASE}/{self.app_id}/agents/{agent_id}/leave", headers=self._headers)

    async def speak(self, agent_id: str, text: str, priority: str = "APPEND",
                    interruptable: bool = True) -> Optional[dict[str, Any]]:
        """Broadcast text via the agent's TTS. priority: INTERRUPT | APPEND | IGNORE."""
        body = {"text": text[:500], "priority": priority, "interruptable": interruptable}
        r = await self._http.post(f"{BASE}/{self.app_id}/agents/{agent_id}/speak",
                                  headers=self._headers, json=body)
        if r.status_code >= 400:
            log.warning("agora speak failed %s %s", r.status_code, r.text)
            return None
        return r.json()

    async def interrupt(self, agent_id: str) -> None:
        await self._http.post(f"{BASE}/{self.app_id}/agents/{agent_id}/interrupt", headers=self._headers)

    async def query(self, agent_id: str) -> dict[str, Any]:
        r = await self._http.get(f"{BASE}/{self.app_id}/agents/{agent_id}", headers=self._headers)
        return r.json()
