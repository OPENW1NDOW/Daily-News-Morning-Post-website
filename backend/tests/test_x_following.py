from datetime import datetime, timezone

from app.api.deps import hash_password, create_access_token
from app.models import User, XAccount, PipelineRun


def _admin_headers(db):
    user = User(username="admin", password_hash=hash_password("x"), is_admin=True)
    db.add(user)
    db.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def test_list_x_following_accounts(client, db):
    headers = _admin_headers(db)
    db.add(XAccount(x_user_id="1", handle="alice", display_name="Alice", enabled=True, is_following=True))
    db.add(XAccount(x_user_id="2", handle="bob", display_name="Bob", enabled=False, is_following=True))
    db.commit()

    resp = client.get("/api/admin/x-following/accounts", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert {a["handle"] for a in data} == {"alice", "bob"}
    assert all("x_user_id" in a and "enabled" in a and "is_following" in a for a in data)


def test_patch_x_following_account_enabled(client, db):
    headers = _admin_headers(db)
    acct = XAccount(x_user_id="1", handle="alice", display_name="Alice", enabled=True, is_following=True)
    db.add(acct)
    db.commit()
    db.refresh(acct)

    resp = client.patch(
        f"/api/admin/x-following/accounts/{acct.id}",
        json={"enabled": False},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["id"] == acct.id

    missing = client.patch(
        "/api/admin/x-following/accounts/99999",
        json={"enabled": True},
        headers=headers,
    )
    assert missing.status_code == 404


def test_x_following_status_shape(client, db, monkeypatch):
    headers = _admin_headers(db)
    monkeypatch.setattr("app.api.admin.settings.x_auth_token", "tok")
    monkeypatch.setattr("app.api.admin.settings.x_ct0", "ct0")

    synced = datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)
    db.add(XAccount(
        x_user_id="1", handle="alice", display_name="Alice",
        enabled=True, is_following=True, last_synced_at=synced,
    ))
    db.add(PipelineRun(
        trigger="manual",
        status="ok",
        result={"following": {"status": "ok", "written": 6, "error": None}},
    ))
    db.commit()

    resp = client.get("/api/admin/x-following/status", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["cookie_configured"] is True
    assert body["last_synced_at"] is not None
    assert body["following"] == {"status": "ok", "written": 6, "error": None}


def test_sync_x_following_with_monkeypatched_list(client, db, monkeypatch):
    headers = _admin_headers(db)
    db.add(XAccount(x_user_id="old", handle="gone", display_name="Gone", enabled=True, is_following=True))
    db.commit()

    monkeypatch.setattr(
        "app.pipeline.sync_x_following.list_following",
        lambda: [
            {"x_user_id": "1", "handle": "alice", "display_name": "Alice", "avatar_url": None},
            {"x_user_id": "2", "handle": "bob", "display_name": "Bob", "avatar_url": None},
        ],
    )

    resp = client.post("/api/admin/x-following/sync", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "count": 2}

    db.expire_all()
    accounts = db.query(XAccount).all()
    by_id = {a.x_user_id: a for a in accounts}
    assert by_id["1"].is_following is True
    assert by_id["2"].is_following is True
    assert by_id["old"].is_following is False


def test_x_following_requires_admin(client, db):
    user = User(username="normal", password_hash=hash_password("x"), is_admin=False)
    db.add(user)
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    assert client.get("/api/admin/x-following/accounts", headers=headers).status_code == 403
    assert client.get("/api/admin/x-following/status", headers=headers).status_code == 403
    assert client.post("/api/admin/x-following/sync", headers=headers).status_code == 403
    assert client.patch(
        "/api/admin/x-following/accounts/1",
        json={"enabled": False},
        headers=headers,
    ).status_code == 403
