"""Outbound email via Resend (https://resend.com). Graceful fallback: if no
API key is configured the email is logged and the caller still gets the invite
link to share manually."""
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger("sentinel.mail")


def configured() -> bool:
    return bool(get_settings().resend_api_key)


async def send(to: str, subject: str, html: str) -> dict:
    s = get_settings()
    if not s.resend_api_key:
        log.info("[mock email] to=%s subject=%s", to, subject)
        return {"mock": True}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://api.resend.com/emails",
                         headers={"Authorization": f"Bearer {s.resend_api_key}"},
                         json={"from": s.resend_from, "to": [to], "subject": subject, "html": html})
        if r.status_code >= 400:
            log.warning("resend failed %s %s", r.status_code, r.text[:200])
            return {"error": r.text[:200]}
        return r.json()


def invite_html(org: str, inviter: str, link: str) -> str:
    return f"""
<div style="font-family:ui-monospace,Menlo,monospace;background:#101114;color:#f4f5f8;padding:40px;border:1px solid #2c2f37">
  <div style="letter-spacing:.3em;font-size:11px;color:#f97316">SENTINEL / BY NERDNINZAS</div>
  <h1 style="font-size:22px;margin:16px 0 8px">You've been invited to <span style="color:#f97316">{org}</span></h1>
  <p style="color:#b6bcc8;font-size:13px;line-height:1.6">{inviter} invited you to join their incident-response workspace on Sentinel —
  the AI incident commander that joins your war room, tracks facts vs hypotheses, and never touches production without a human.</p>
  <a href="{link}" style="display:inline-block;margin-top:20px;background:#f97316;color:#000;padding:12px 22px;text-decoration:none;font-weight:600;letter-spacing:.15em;font-size:12px">ACCEPT INVITATION →</a>
  <p style="color:#838a97;font-size:11px;margin-top:24px">Or paste this link in your browser:<br>{link}</p>
</div>"""
