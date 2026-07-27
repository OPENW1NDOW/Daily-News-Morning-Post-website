"""认证 API：注册、登录、用户信息。"""
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .deps import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()

# ── 内存滑动窗口限流（按 IP，重启即重置） ──────────────────
_rate_buckets: dict[str, list[float]] = {}
_rate_lock = threading.Lock()
_MAX_WINDOW_SECONDS = 3600


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(bucket: str, ip: str, limit: int, window_seconds: int, message: str):
    now = time.time()
    key = f"{bucket}:{ip}"
    with _rate_lock:
        if len(_rate_buckets) > 1000:
            for k in [k for k, ts in _rate_buckets.items() if all(now - t >= _MAX_WINDOW_SECONDS for t in ts)]:
                del _rate_buckets[k]
        timestamps = [t for t in _rate_buckets.get(key, []) if now - t < window_seconds]
        if len(timestamps) >= limit:
            _rate_buckets[key] = timestamps
            raise HTTPException(429, message)
        timestamps.append(now)
        _rate_buckets[key] = timestamps


class RegisterIn(BaseModel):
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/api/auth/register")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit("register", _client_ip(request), 3, 3600, "注册过于频繁，请一小时后再试")
    if len(body.username) < 2 or len(body.username) > 20:
        raise HTTPException(400, "用户名长度 2-20 个字符")
    # 最小长度仅约束新注册，现有用户登录不受影响
    if len(body.password) < 8:
        raise HTTPException(400, "密码至少 8 个字符")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {"token": token, "user": {"id": user.id, "username": user.username, "is_admin": user.is_admin}}


@router.post("/api/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    _check_rate_limit("login", _client_ip(request), 5, 60, "登录尝试过于频繁，请稍后再试")
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    token = create_access_token(user.id)
    return {"token": token, "user": {"id": user.id, "username": user.username, "is_admin": user.is_admin}}


@router.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(401, "未登录")
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}
