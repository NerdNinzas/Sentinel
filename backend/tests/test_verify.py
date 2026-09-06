import asyncio
from datetime import timedelta

import pytest

from app.engine import models as m
from app.engine.engine import engine
from app.engine.store import store
from app.tools import github as gh


@pytest.mark.asyncio
async def test_claim_verified_when_commit_exists(monkeypatch):
    inc = store.create("Verify test", m.Severity.SEV2, "vc1")
    inc.repo = "acme/payments"
    store.add_participant(inc, "rahul", "Rahul Sharma", m.Role.BACKEND)

    fresh = (m.now() - timedelta(minutes=5)).isoformat()
    async def fake_changes(repo, start, token=None):
        return {"commits": [{"sha": "abc1234", "message": "fix pool leak", "author": "rahul-dev",
                             "url": "https://github.com/acme/payments/commit/abc1234", "at": fresh,
                             "minutes_before_incident": -5, "suspect": False}]}
    monkeypatch.setattr(gh, "fetch_changes", fake_changes)
    await engine.verify_claim(inc, "rahul", "I've completed the backend part and pushed it")
    assert any(f.text.startswith("Verified: Rahul") for f in inc.facts)
    said = [l.text for l in inc.transcript if l.uid == "sentinel"]
    assert any("checks out" in t for t in said)


@pytest.mark.asyncio
async def test_claim_flagged_when_no_commit(monkeypatch):
    inc = store.create("Verify test 2", m.Severity.SEV2, "vc2")
    inc.repo = "acme/payments"
    store.add_participant(inc, "ananya", "Ananya R", m.Role.SRE)

    async def fake_changes(repo, start, token=None):
        return {"commits": []}
    monkeypatch.setattr(gh, "fetch_changes", fake_changes)
    await engine.verify_claim(inc, "ananya", "deployed the config fix")
    assert any("Unverified claim: Ananya" in r.text for r in inc.risks)
    said = [l.text for l in inc.transcript if l.uid == "sentinel"]
    assert any("couldn't verify" in t for t in said)
