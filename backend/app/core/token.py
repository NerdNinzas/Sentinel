"""Agora RTC + RTM token generation (AccessToken2 / '007')."""
from __future__ import annotations

from app.core.config import get_settings
from app.core.access_token2 import AccessToken, ServiceRtc, ServiceRtm


def build_tokens(channel: str, uid: str, expire_seconds: int = 6 * 3600) -> dict[str, str]:
    """Return {'rtc': ..., 'rtm': ...}. Empty strings when the project has no
    certificate (Agora 'testing mode' projects accept null tokens)."""
    s = get_settings()
    if not s.agora_app_certificate:
        return {"rtc": "", "rtm": ""}
    tok = AccessToken(s.agora_app_id, s.agora_app_certificate, expire=expire_seconds)
    rtc = ServiceRtc(channel, uid)
    rtc.add_privilege(ServiceRtc.kPrivilegeJoinChannel, expire_seconds)
    rtc.add_privilege(ServiceRtc.kPrivilegePublishAudioStream, expire_seconds)
    rtc.add_privilege(ServiceRtc.kPrivilegePublishDataStream, expire_seconds)
    tok.add_service(rtc)
    rtm = ServiceRtm(uid)
    rtm.add_privilege(ServiceRtm.kPrivilegeLogin, expire_seconds)
    tok.add_service(rtm)
    t = tok.build()
    return {"rtc": t, "rtm": t}
