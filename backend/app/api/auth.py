from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core import accounts, auth, db, mailer
from app.core.config import get_settings
from app.engine.store import store

router = APIRouter(prefix="/api", tags=["auth"])


# ---- email/password auth ---------------------------------------------------
class SignupBody(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/auth/signup")
async def signup(body: SignupBody):
    return await accounts.signup(body.email, body.password, body.name)


@router.post("/auth/login")
async def login(body: LoginBody):
    return await accounts.login(body.email, body.password)


class OnboardBody(BaseModel):
    account_type: str                 # "personal" | "organization"
    org_name: str = ""
    org_address: str = ""
    org_website: str = ""


@router.post("/auth/onboard")
async def onboard(body: OnboardBody, user: dict = Depends(auth.require_user)):
    if body.account_type not in ("personal", "organization"):
        raise HTTPException(400, "account_type must be personal or organization")
    return await accounts.onboard(user, body.account_type, body.org_name, body.org_address, body.org_website)


@router.get("/auth/me")
async def me(user: Optional[dict] = Depends(auth.current_user)):
    if not user:
        raise HTTPException(401, "not signed in")
    return accounts.public_user(user)


@router.post("/auth/notice-ack")
async def notice_ack(user: dict = Depends(auth.require_user)):
    await accounts.ack_notice(user)
    return {"ok": True}


@router.post("/auth/logout")
async def logout():
    return {"ok": True}


# ---- organization & invitations -------------------------------------------
@router.get("/org")
async def org(user: dict = Depends(auth.require_user)):
    return await accounts.org_overview(user)


class InviteBody(BaseModel):
    email: Optional[str] = None


@router.post("/org/invites")
async def create_invite(body: InviteBody, user: dict = Depends(auth.require_user)):
    s = get_settings()
    inv = await accounts.create_invite(user, body.email, s.frontend_url)
    emailed = False
    if body.email:
        res = await mailer.send(body.email, f"{user.get('name')} invited you to {user.get('org_name')} on Sentinel",
                                mailer.invite_html(user.get("org_name") or "their workspace", user.get("name") or "A teammate", inv["link"]))
        emailed = not res.get("error") and not res.get("mock")
    return {**inv, "emailed": emailed, "mail_configured": mailer.configured()}


@router.get("/invites/{token}")
async def invite_info(token: str):
    return await accounts.invite_info(token)


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, user: dict = Depends(auth.require_user)):
    return await accounts.accept_invite(user, token)


# ---- GitHub as an integration ----------------------------------------------
class PatBody(BaseModel):
    token: str


@router.post("/integrations/github")
async def connect_github(body: PatBody, user: dict = Depends(auth.require_user)):
    gh = await auth.github_user(body.token.strip())
    patch = {"github_token": body.token.strip(), "github_login": gh["login"],
             "avatar_url": user.get("avatar_url") or gh.get("avatar_url"), "html_url": gh.get("html_url")}
    if db.available():
        await db.db().users.update_one({"_id": user["_id"]}, {"$set": patch})
    user.update(patch)
    return accounts.public_user(user)


@router.delete("/integrations/github")
async def disconnect_github(user: dict = Depends(auth.require_user)):
    if db.available():
        await db.db().users.update_one({"_id": user["_id"]}, {"$unset": {"github_token": "", "github_login": ""}})
    user.pop("github_token", None), user.pop("github_login", None)
    return accounts.public_user(user)


@router.get("/auth/github/login")
async def oauth_login(session: str = ""):
    s = get_settings()
    if not s.github_oauth_client_id:
        raise HTTPException(400, "GitHub OAuth app not configured — paste a classic token instead")
    url = ("https://github.com/login/oauth/authorize"
           f"?client_id={s.github_oauth_client_id}&scope=repo%20read:user"
           f"&redirect_uri={s.public_base_url}/api/auth/github/callback&state={session}")
    return RedirectResponse(url)


@router.get("/auth/github/callback")
async def oauth_callback(code: str, state: str = ""):
    s = get_settings()
    gh_token = await auth.oauth_exchange(code)
    user = await auth.resolve(f"Bearer {state}") if state else None
    if user:   # attach GitHub to the signed-in account
        gh = await auth.github_user(gh_token)
        patch = {"github_token": gh_token, "github_login": gh["login"],
                 "avatar_url": user.get("avatar_url") or gh.get("avatar_url"), "html_url": gh.get("html_url")}
        if db.available():
            await db.db().users.update_one({"_id": user["_id"]}, {"$set": patch})
        user.update(patch)
        return RedirectResponse(f"{s.frontend_url}/dashboard#integrations")
    return RedirectResponse(f"{s.frontend_url}/login")


@router.get("/github/repos")
async def list_repos(user: dict = Depends(auth.require_user)):
    tok = user.get("github_token") or get_settings().github_token
    if not tok:
        return []
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://api.github.com/user/repos",
                        params={"sort": "pushed", "per_page": 40, "affiliation": "owner,collaborator,organization_member"},
                        headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
        r.raise_for_status()
        return [{"full_name": x["full_name"], "private": x["private"], "pushed_at": x.get("pushed_at"),
                 "default_branch": x.get("default_branch"), "description": (x.get("description") or "")[:80]} for x in r.json()]


@router.get("/me/rooms")
async def my_rooms(user: dict = Depends(auth.require_user)):
    rooms = await db.user_rooms(user["_id"])
    out: list[dict[str, Any]] = []
    for r in rooms:
        inc = store.incidents.get(r["incident_id"])
        meta = ({"title": inc.title, "severity": inc.severity, "status": inc.status, "repo": inc.repo,
                 "started_at": inc.started_at, "counts": inc.counts()} if inc else {})
        out.append({**r, **{k: (v if not hasattr(v, "value") else v.value) for k, v in meta.items()}})
    return out


@router.get("/integrations")
async def integrations(user: dict = Depends(auth.require_user)):
    s = get_settings()
    return {
        "github": {"connected": bool(user.get("github_token")), "login": user.get("github_login")},
        "slack": {"connected": bool(s.slack_bot_token), "channel": s.slack_channel, "status": "arriving tomorrow" if not s.slack_bot_token else "live"},
        "jira": {"connected": bool(s.jira_api_token), "project": s.jira_project_key, "status": "arriving tomorrow" if not s.jira_api_token else "live"},
        "email": {"connected": mailer.configured()},
        "mongodb": {"connected": db.available()},
        "agora": {"connected": bool(s.agora_app_id)},
        "llm": {"connected": bool(s.llm_api_key), "model": s.llm_model},
    }
