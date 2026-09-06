"""Integration adapters. Each one talks to the real API when configured and
falls back to a realistic mock otherwise, so the demo never blocks on creds."""
from __future__ import annotations

import asyncio
import logging
import random

import httpx

from app.core.config import get_settings
from app.engine import models as m
from app.mock.monitoring import monitoring  # re-exported for the gateway

log = logging.getLogger("sentinel.adapters")


class Slack:
    def __init__(self) -> None:
        self._channel_id: str | None = None
        self._bot_user: str | None = None
        self._users: dict[str, str] = {}

    def _hdr(self) -> dict:
        return {"Authorization": f"Bearer {get_settings().slack_bot_token}"}

    async def channel_id(self) -> str | None:
        if self._channel_id:
            return self._channel_id
        name = get_settings().slack_channel.lstrip("#")
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://slack.com/api/conversations.list", headers=self._hdr(),
                            params={"types": "public_channel", "limit": 200})
            for ch in r.json().get("channels", []):
                if ch["name"] == name:
                    self._channel_id = ch["id"]
            a = await c.get("https://slack.com/api/auth.test", headers=self._hdr())
            self._bot_user = a.json().get("user_id")
        return self._channel_id

    async def user_name(self, uid: str) -> str:
        if uid in self._users:
            return self._users[uid]
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://slack.com/api/users.info", headers=self._hdr(), params={"user": uid})
            name = (r.json().get("user") or {}).get("real_name") or uid
        self._users[uid] = name
        return name

    async def history(self, oldest: float) -> list[dict]:
        """New human messages in the incident channel since `oldest` (epoch seconds)."""
        ch = await self.channel_id()
        if not ch:
            return []
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://slack.com/api/conversations.history", headers=self._hdr(),
                            params={"channel": ch, "oldest": f"{oldest:.6f}", "limit": 50})
        out = []
        for msg in reversed(r.json().get("messages", [])):
            if msg.get("bot_id") or msg.get("subtype") or msg.get("user") == self._bot_user:
                continue
            if msg.get("text"):
                out.append({"user": msg["user"], "text": msg["text"], "ts": float(msg["ts"])})
        return out

    async def post(self, inc: m.Incident, text: str) -> dict:
        s = get_settings()
        if not s.slack_bot_token:
            log.info("[mock slack] %s: %s", s.slack_channel, text)
            return {"summary": f"posted to {s.slack_channel} (mock)", "text": text, "mock": True}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://slack.com/api/chat.postMessage",
                             headers={"Authorization": f"Bearer {s.slack_bot_token}"},
                             json={"channel": s.slack_channel, "text": f"*[{inc.id} {inc.severity.value}]* {text}"})
            data = r.json()
            return {"summary": f"posted to {s.slack_channel}", "ok": data.get("ok"), "ts": data.get("ts")}


class Jira:
    def __init__(self) -> None:
        self._n = 100

    def _auth(self):
        s = get_settings()
        return (s.jira_email, s.jira_api_token)

    @property
    def configured(self) -> bool:
        s = get_settings()
        return bool(s.jira_base_url and s.jira_api_token)

    async def open_issues(self, limit: int = 8) -> list[dict]:
        """Open issues in the incident project: key, summary, assignee, status."""
        s = get_settings()
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=15, auth=self._auth()) as c:
            r = await c.get(f"{s.jira_base_url}/rest/api/3/search/jql", params={
                "jql": f"project={s.jira_project_key} AND statusCategory != Done ORDER BY updated DESC",
                "maxResults": limit, "fields": "summary,assignee,status"})
            if r.status_code >= 400:
                return []
            return [{"key": i["key"], "summary": i["fields"]["summary"][:60],
                     "assignee": (i["fields"].get("assignee") or {}).get("displayName"),
                     "status": i["fields"]["status"]["name"]} for i in r.json().get("issues", [])]

    async def issues_for(self, person: str, limit: int = 5) -> list[dict]:
        """Issues assigned to a person (matched by display name)."""
        s = get_settings()
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=15, auth=self._auth()) as c:
            u = await c.get(f"{s.jira_base_url}/rest/api/3/user/search", params={"query": person})
            users = [x for x in u.json() if x.get("accountType") == "atlassian"] if u.status_code < 400 else []
            if not users:
                return []
            acct = users[0]["accountId"]
            r = await c.get(f"{s.jira_base_url}/rest/api/3/search/jql", params={
                "jql": f"assignee = {acct} ORDER BY updated DESC", "maxResults": limit,
                "fields": "summary,status,updated"})
            if r.status_code >= 400:
                return []
            return [{"key": i["key"], "summary": i["fields"]["summary"][:60],
                     "status": i["fields"]["status"]["name"], "assignee": users[0].get("displayName")}
                    for i in r.json().get("issues", [])]

    async def create(self, inc: m.Incident, summary: str, assignee: str | None, description: str) -> dict:
        s = get_settings()
        if not (s.jira_base_url and s.jira_api_token):
            self._n += 1
            key = f"{s.jira_project_key}-{self._n}"
            return {"summary": f"created {key} (mock)", "key": key, "url": f"https://jira.example.com/browse/{key}", "assignee": assignee, "mock": True}
        async with httpx.AsyncClient(timeout=15, auth=(s.jira_email, s.jira_api_token)) as c:
            r = await c.post(f"{s.jira_base_url}/rest/api/3/issue", json={"fields": {
                "project": {"key": s.jira_project_key}, "summary": f"[{inc.id}] {summary}",
                "issuetype": {"name": "Task"},
                "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description or summary}]}]},
            }})
            data = r.json()
            key = data.get("key", "?")
            return {"summary": f"created {key}", "key": key, "url": f"{s.jira_base_url}/browse/{key}"}


class PagerDuty:
    async def page(self, inc: m.Incident, team: str, reason: str) -> dict:
        s = get_settings()
        if not s.pagerduty_api_key:
            return {"summary": f"paged {team} on-call (mock)", "team": team, "mock": True}
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://api.pagerduty.com/incidents",
                             headers={"Authorization": f"Token token={s.pagerduty_api_key}",
                                      "Accept": "application/vnd.pagerduty+json;version=2",
                                      "From": s.jira_email or "sentinel@example.com"},
                             json={"incident": {"type": "incident", "title": f"[{inc.id}] {reason or inc.title}",
                                                "service": {"id": s.pagerduty_service_id, "type": "service_reference"}}})
            return {"summary": f"paged {team}", "status": r.status_code}


class Deploy:
    """Mock deployment controller. Rollback drives the mock monitoring to recovery."""

    async def rollback(self, inc: m.Incident, service: str, version: str | None) -> dict:
        await asyncio.sleep(1.5 / monitoring.speed)
        asyncio.create_task(monitoring.recover_over(seconds=10))
        return {"summary": f"rolled back {service} {version or ''} → v4.1".replace("  ", " "), "service": service, "to": "v4.1"}

    async def restart(self, inc: m.Incident, service: str) -> dict:
        await asyncio.sleep(1)
        return {"summary": f"restarted {service}", "pods": random.randint(3, 8)}

    async def failover(self, inc: m.Incident, database: str) -> dict:
        await asyncio.sleep(2)
        return {"summary": f"failed over {database} to replica-b"}

    async def scale(self, inc: m.Incident, service: str, replicas: int) -> dict:
        await asyncio.sleep(1)
        return {"summary": f"scaled {service} to {replicas} replicas"}

    async def disable_flag(self, inc: m.Incident, flag: str) -> dict:
        return {"summary": f"disabled flag {flag}"}


slack, jira, pagerduty, deploy = Slack(), Jira(), PagerDuty(), Deploy()
