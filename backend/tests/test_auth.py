"""认证测试：注册/登录/me + token 边界（过期、错签名）与鉴权依赖。"""
from datetime import datetime, timedelta, timezone

from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.api.deps import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    get_current_user,
    hash_password,
)
from app.models import User

PASSWORD = "longpass123"  # 注册最小密码长度已提升到 8


def _register(client, username="alice", password=PASSWORD):
    return client.post("/api/auth/register", json={"username": username, "password": password})


class TestRegister:
    def test_register_success(self, client):
        resp = _register(client)
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"]
        assert data["user"]["username"] == "alice"
        assert data["user"]["is_admin"] is False

    def test_short_username_400(self, client):
        assert _register(client, username="a").status_code == 400

    def test_short_password_400(self, client):
        assert _register(client, password="1234567").status_code == 400

    def test_duplicate_username_400(self, client):
        assert _register(client).status_code == 200
        resp = _register(client)
        assert resp.status_code == 400
        assert "已存在" in resp.json()["detail"]


class TestLogin:
    def test_login_success(self, client):
        _register(client)
        resp = client.post("/api/auth/login", json={"username": "alice", "password": PASSWORD})
        assert resp.status_code == 200
        assert resp.json()["token"]

    def test_wrong_password_401(self, client):
        _register(client)
        resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass1"})
        assert resp.status_code == 401


class TestMe:
    def test_me_with_token(self, client):
        token = _register(client).json()["token"]
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "alice"

    def test_me_without_token_401(self, client):
        assert client.get("/api/auth/me").status_code == 401


# ---------- token 边界 ----------

def _expired_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) - timedelta(hours=1)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _wrong_signature_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode({"sub": str(user_id), "exp": expire}, "another-secret", algorithm=ALGORITHM)


def _make_user(db, username="bob", is_admin=False) -> User:
    user = User(username=username, password_hash=hash_password(PASSWORD), is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestTokenBoundaries:
    def test_get_current_user_returns_none_for_bad_tokens(self, db):
        user = _make_user(db)
        for bad in (_expired_token(user.id), _wrong_signature_token(user.id), "not-a-jwt"):
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad)
            assert get_current_user(credentials=creds, db=db) is None

        good = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_access_token(user.id)
        )
        assert get_current_user(credentials=good, db=db).id == user.id

    def test_require_user_401_for_bad_tokens(self, client, db):
        user = _make_user(db)
        for bad in (_expired_token(user.id), _wrong_signature_token(user.id)):
            resp = client.get("/api/favorites", headers={"Authorization": f"Bearer {bad}"})
            assert resp.status_code == 401

    def test_require_admin_403_for_normal_user(self, client, db):
        user = _make_user(db, username="normal_user")
        headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
        assert client.get("/api/admin/dashboard", headers=headers).status_code == 403
