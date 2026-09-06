"""GitHub-only authentication.

Two paths to the same session:
  * OAuth (Sign in with GitHub)  — needs GITHUB_OAUTH_CLIENT_ID/SECRET
  * Classic PAT paste            — works with zero setup (scopes: repo, read:user)
Sessions live in Mongo (+ a process cache); the bearer token goes in the
Authorization header.
"""
from __future__ import annotations

import logging
import secrets
from typing import Any, Optional

import httpx
from fastapi import Header, HTTPException

from app.core import db
from app.core.config import get_settings

log = logging.getLogger("sentinel.auth")
_cache: dict[str, dict[str, Any]] = {}     # session token -> user doc


async def github_user(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get("https://api.github.com/user",
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            raise HTTPException(401, "GitHub rejected that token")
        return r.json()


async def login_with_token(gh_token: str) -> dict[str, Any]:
    gh = await github_user(gh_token)
    user = await db.upsert_user(gh, gh_token)
    session = "st_" + secrets.token_urlsafe(24)
    await db.create_session(user["_id"], session)
    _cache[session] = user
    return {"session": session, "user": public_user(user)}


async def oauth_exchange(code: str) -> str:
    s = get_settings()
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post("https://github.com/login/oauth/access_token",
                         headers={"Accept": "application/json"},
                         data={"client_id": s.github_oauth_client_id, "client_secret": s.github_oauth_client_secret, "code": code})
        tok = r.json().get("access_token")
        if not tok:
            raise HTTPException(401, f"OAuth exchange failed: {r.text[:200]}")
        return tok


def public_user(u: dict[str, Any]) -> dict[str, Any]:
    return {"id": u["_id"], "login": u["login"], "name": u.get("name"), "avatar_url": u.get("avatar_url"), "html_url": u.get("html_url")}


async def resolve(authorization: Optional[str]) -> Optional[dict[str, Any]]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    tok = authorization.removeprefix("Bearer ").strip()
    if tok in _cache:
        return _cache[tok]
    u = await db.get_session_user(tok)
    if u:
        _cache[tok] = u
    return u


async def current_user(authorization: Optional[str] = Header(default=None)) -> Optional[dict[str, Any]]:
    return await resolve(authorization)


async def require_user(authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    u = await resolve(authorization)
    if u is None:
        if get_settings().auth_required:
            raise HTTPException(401, "Sign in with GitHub first")
        return {"_id": 0, "login": "guest", "name": "Guest", "github_token": ""}
    return u
