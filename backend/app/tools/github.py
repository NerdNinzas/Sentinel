"""GitHub adapter: the incident's linked repo, read as *evidence*.

Scope is deliberately narrow — recent changes around the incident window, not
the whole repo: commits on the default branch, recently merged PRs, latest
release, failed workflow runs. Public repos need no token; set GITHUB_TOKEN
for private repos / higher rate limits.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.engine import models as m

log = logging.getLogger("sentinel.github")
API = "https://api.github.com"
WINDOW_HOURS = 24          # look-back before incident start



def _headers(token: str | None = None) -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "sentinel-incident-commander"}
    if (t := token or get_settings().github_token):
        h["Authorization"] = f"Bearer {t}"
    return h


async def fetch_changes(repo: str, incident_start: m.datetime, token: str | None = None) -> dict[str, Any]:
    """Return {branch, commits[], merged_prs[], failed_runs[], release} for the window."""
    since = (incident_start - timedelta(hours=WINDOW_HOURS)).isoformat()
    out: dict[str, Any] = {"repo": repo, "branch": None, "commits": [], "merged_prs": [], "failed_runs": [], "release": None, "error": None}
    async with httpx.AsyncClient(timeout=15, headers=_headers(token)) as c:
        try:
            r = await c.get(f"{API}/repos/{repo}")
            if r.status_code == 404:
                out["error"] = "repo not found (private? set GITHUB_TOKEN)"
                return out
            r.raise_for_status()
            out["branch"] = r.json().get("default_branch", "main")

            rc = await c.get(f"{API}/repos/{repo}/commits", params={"sha": out["branch"], "since": since, "per_page": 20})
            if rc.status_code == 409:      # empty repository
                out["error"] = "repository is empty"
                return out
            rc.raise_for_status()
            for it in rc.json():
                commit = it.get("commit", {})
                # committer date ~ push/merge time (author date can be days older after rebase)
                at = commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")
                mins = None
                if at:
                    mins = round((incident_start - m.datetime.fromisoformat(at.replace("Z", "+00:00"))).total_seconds() / 60)
                out["commits"].append({
                    "sha": (it.get("sha") or "")[:7],
                    "message": (commit.get("message") or "").splitlines()[0][:100],
                    "author": (it.get("author") or {}).get("login") or commit.get("author", {}).get("name") or "?",
                    "url": it.get("html_url"),
                    "at": at,
                    "minutes_before_incident": mins,
                    "suspect": mins is not None and -get_settings().github_suspect_minutes <= mins <= get_settings().github_suspect_minutes,
                })

            rp = await c.get(f"{API}/repos/{repo}/pulls", params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 10, "base": out["branch"]})
            if rp.status_code < 400:
                for pr in rp.json():
                    ma = pr.get("merged_at")
                    if not ma or ma < since:
                        continue
                    mins = round((incident_start - m.datetime.fromisoformat(ma.replace("Z", "+00:00"))).total_seconds() / 60)
                    out["merged_prs"].append({
                        "number": pr["number"], "title": pr["title"][:100], "author": (pr.get("user") or {}).get("login", "?"),
                        "url": pr.get("html_url"), "merged_at": ma, "minutes_before_incident": mins,
                        "suspect": -get_settings().github_suspect_minutes <= mins <= get_settings().github_suspect_minutes,
                    })

            rr = await c.get(f"{API}/repos/{repo}/releases/latest")
            if rr.status_code < 400:
                rel = rr.json()
                out["release"] = {"tag": rel.get("tag_name"), "url": rel.get("html_url"), "at": rel.get("published_at")}

            ra = await c.get(f"{API}/repos/{repo}/actions/runs", params={"status": "failure", "per_page": 5, "created": f">={since[:10]}"})
            if ra.status_code < 400:
                for run in ra.json().get("workflow_runs", []):
                    out["failed_runs"].append({"name": run.get("name"), "url": run.get("html_url"), "branch": run.get("head_branch"), "at": run.get("created_at")})
        except httpx.HTTPError as e:
            out["error"] = f"github fetch failed: {e}"
            log.warning("github %s: %s", repo, e)
    return out


async def create_issue(repo: str, title: str, body: str) -> dict[str, Any]:
    if not get_settings().github_token:
        return {"summary": f"created issue on {repo} (mock — no GITHUB_TOKEN)", "mock": True, "title": title}
    async with httpx.AsyncClient(timeout=15, headers=_headers()) as c:
        r = await c.post(f"{API}/repos/{repo}/issues", json={"title": title, "body": body})
        r.raise_for_status()
        d = r.json()
        return {"summary": f"created issue #{d['number']} on {repo}", "url": d["html_url"], "number": d["number"]}


async def comment_on_pr(repo: str, number: int, body: str) -> dict[str, Any]:
    if not get_settings().github_token:
        return {"summary": f"commented on {repo}#{number} (mock — no GITHUB_TOKEN)", "mock": True}
    async with httpx.AsyncClient(timeout=15, headers=_headers()) as c:
        r = await c.post(f"{API}/repos/{repo}/issues/{number}/comments", json={"body": body})
        r.raise_for_status()
        return {"summary": f"commented on {repo}#{number}", "url": r.json().get("html_url")}


async def _any_write_token() -> Optional[str]:
    from app.core import db
    if db.available():
        u = await db.db().users.find_one({"github_token": {"$nin": [None, ""]}})
        if u:
            return u["github_token"]
    return get_settings().github_token or None


async def open_revert_pr(repo: str, sha: str, reason: str) -> dict[str, Any]:
    """Critical tool (human-gated upstream): create a real revert of the suspect
    commit, open a PR, and merge it — the deploy platform then auto-redeploys.
    Works when the suspect commit is at/near HEAD (we reset the tree to its parent)."""
    token = await _any_write_token()
    if not token:
        return {"summary": f"opened revert PR for {sha} on {repo} (mock — connect GitHub with a repo-scope token)", "mock": True, "sha": sha, "reason": reason}
    async with httpx.AsyncClient(timeout=30, headers=_headers(token)) as c:
        info = (await c.get(f"{API}/repos/{repo}")).json()
        base = info.get("default_branch", "main")
        head_sha = (await c.get(f"{API}/repos/{repo}/commits/{base}")).json()["sha"]
        bad = (await c.get(f"{API}/repos/{repo}/commits/{sha}")).json()
        parent_sha = bad["parents"][0]["sha"]
        parent_tree = (await c.get(f"{API}/repos/{repo}/git/commits/{parent_sha}")).json()["tree"]["sha"]
        branch = f"sentinel/revert-{sha[:7]}"
        r = await c.post(f"{API}/repos/{repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": head_sha})
        if r.status_code == 422 and "already exists" in r.text:
            pass
        elif r.status_code >= 400:
            return {"summary": f"revert failed creating branch: {r.text[:120]}", "error": r.text[:200]}
        commit = await c.post(f"{API}/repos/{repo}/git/commits", json={
            "message": f"Revert \"{bad['commit']['message'].splitlines()[0][:60]}\"\n\nProposed by Sentinel during an incident. {reason[:140]}",
            "tree": parent_tree, "parents": [head_sha]})
        commit.raise_for_status()
        await c.patch(f"{API}/repos/{repo}/git/refs/heads/{branch}", json={"sha": commit.json()["sha"], "force": True})
        pr = await c.post(f"{API}/repos/{repo}/pulls", json={
            "title": f"Revert {sha[:7]}: incident mitigation", "head": branch, "base": base,
            "body": f"Opened by **Sentinel** after human approval in the war room.\n\nReason: {reason}\n\nReverts `{sha[:7]}` — merging triggers auto-deploy."})
        if pr.status_code >= 400:
            return {"summary": f"revert branch pushed but PR failed: {pr.text[:120]}", "branch": branch}
        n = pr.json()["number"]
        mg = await c.put(f"{API}/repos/{repo}/pulls/{n}/merge", json={"merge_method": "merge"})
        merged = mg.status_code < 400
        return {"summary": f"revert PR #{n} opened{' and merged — redeploy in progress' if merged else ' (merge manually)'}",
                "pr": n, "url": pr.json()["html_url"], "merged": merged, "sha": sha}
