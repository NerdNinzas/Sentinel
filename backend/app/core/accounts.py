"""Email/password accounts + organizations + invitations (MongoDB)."""
from __future__ import annotations

import hashlib
import re
import secrets
from typing import Any, Optional

from fastapi import HTTPException

from app.core import db
from app.core.auth import _cache  # session cache shared with bearer resolution


# ---- passwords -------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        _, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def _require_db() -> None:
    if not db.available():
        raise HTTPException(503, "database unavailable — accounts need MongoDB")


def public_user(u: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": u["_id"], "email": u.get("email"), "name": u.get("name") or u.get("login"),
        "login": u.get("login") or (u.get("email") or "").split("@")[0],
        "avatar_url": u.get("avatar_url"), "html_url": u.get("html_url"),
        "account_type": u.get("account_type"), "onboarded": bool(u.get("onboarded")),
        "org_id": u.get("org_id"), "org_name": u.get("org_name"),
        "org_role": u.get("org_role"), "org_notice": u.get("org_notice"),
        "github_connected": bool(u.get("github_token")), "github_login": u.get("github_login"),
    }


async def _session_for(user: dict[str, Any]) -> dict[str, Any]:
    token = "st_" + secrets.token_urlsafe(24)
    await db.create_session(user["_id"], token)
    _cache[token] = user
    return {"session": token, "user": public_user(user)}


# ---- signup / login --------------------------------------------------------
async def signup(email: str, password: str, name: str) -> dict[str, Any]:
    _require_db()
    email = email.strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise HTTPException(400, "enter a valid email")
    if len(password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    if await db.db().users.find_one({"email": email}):
        raise HTTPException(409, "an account with this email already exists — sign in instead")
    uid = "u_" + secrets.token_hex(8)
    doc = {"_id": uid, "email": email, "name": name.strip() or email.split("@")[0],
           "login": email.split("@")[0], "password": hash_password(password),
           "onboarded": False, "account_type": None, "org_id": None,
           "created_at": db.now(), "updated_at": db.now()}
    await db.db().users.insert_one(doc)
    return await _session_for(doc)


async def login(email: str, password: str) -> dict[str, Any]:
    _require_db()
    u = await db.db().users.find_one({"email": email.strip().lower()})
    if not u or not verify_password(password, u.get("password", "")):
        raise HTTPException(401, "wrong email or password")
    return await _session_for(u)


async def onboard(user: dict[str, Any], account_type: str, org_name: str = "",
                  org_address: str = "", org_website: str = "") -> dict[str, Any]:
    _require_db()
    patch: dict[str, Any] = {"account_type": account_type, "onboarded": True, "updated_at": db.now()}
    if account_type == "organization":
        if not org_name.strip():
            raise HTTPException(400, "organization name is required")
        org_id = "org_" + secrets.token_hex(6)
        await db.db().orgs.insert_one({"_id": org_id, "name": org_name.strip(),
                                       "address": org_address.strip(), "website": org_website.strip(),
                                       "created_by": user["_id"], "created_at": db.now()})
        patch.update({"org_id": org_id, "org_name": org_name.strip(), "org_role": "owner"})
    await db.db().users.update_one({"_id": user["_id"]}, {"$set": patch})
    user.update(patch)
    return public_user(user)


# ---- organization ----------------------------------------------------------
async def org_overview(user: dict[str, Any]) -> dict[str, Any]:
    _require_db()
    if not user.get("org_id"):
        return {"org": None, "members": [], "invites": []}
    org = await db.db().orgs.find_one({"_id": user["org_id"]})
    members = [public_user(m) async for m in db.db().users.find({"org_id": user["org_id"]})]
    invites = [{"token": i["_id"], "email": i.get("email"), "status": i["status"],
                "invited_by": i.get("invited_by_name"), "created_at": i.get("created_at")}
               async for i in db.db().invites.find({"org_id": user["org_id"]}).sort("created_at", -1).limit(20)]
    return {"org": {"id": org["_id"], "name": org["name"], "address": org.get("address"), "website": org.get("website")} if org else None,
            "members": members, "invites": invites}


async def create_invite(user: dict[str, Any], email: Optional[str], frontend_url: str) -> dict[str, Any]:
    _require_db()
    if not user.get("org_id"):
        raise HTTPException(400, "create an organization workspace first")
    token = "inv_" + secrets.token_urlsafe(18)
    await db.db().invites.insert_one({"_id": token, "org_id": user["org_id"], "org_name": user.get("org_name"),
                                      "email": (email or "").strip().lower() or None,
                                      "invited_by": user["_id"], "invited_by_name": user.get("name"),
                                      "status": "pending", "created_at": db.now()})
    link = f"{frontend_url}/invite/{token}"
    return {"token": token, "link": link}


async def invite_info(token: str) -> dict[str, Any]:
    _require_db()
    inv = await db.db().invites.find_one({"_id": token})
    if not inv:
        raise HTTPException(404, "invitation not found or revoked")
    return {"org_name": inv.get("org_name"), "invited_by": inv.get("invited_by_name"),
            "status": inv["status"], "email": inv.get("email")}


async def accept_invite(user: dict[str, Any], token: str) -> dict[str, Any]:
    _require_db()
    inv = await db.db().invites.find_one({"_id": token})
    if not inv:
        raise HTTPException(404, "invitation not found")
    if inv["status"] == "accepted":
        raise HTTPException(409, "this invitation was already used")
    patch = {"org_id": inv["org_id"], "org_name": inv.get("org_name"), "org_role": "member",
             "org_notice": f"You have been added to {inv.get('org_name')}", "onboarded": True,
             "account_type": user.get("account_type") or "organization", "updated_at": db.now()}
    await db.db().users.update_one({"_id": user["_id"]}, {"$set": patch})
    await db.db().invites.update_one({"_id": token}, {"$set": {"status": "accepted", "accepted_by": user["_id"], "accepted_at": db.now()}})
    user.update(patch)
    return public_user(user)


async def ack_notice(user: dict[str, Any]) -> None:
    _require_db()
    await db.db().users.update_one({"_id": user["_id"]}, {"$unset": {"org_notice": ""}})
    user.pop("org_notice", None)
