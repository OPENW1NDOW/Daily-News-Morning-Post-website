"""认证 API：注册、登录、用户信息。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .deps import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter()


class RegisterIn(BaseModel):
    username: str
    password: str


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/api/auth/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if len(body.username) < 2 or len(body.username) > 20:
        raise HTTPException(400, "用户名长度 2-20 个字符")
    if len(body.password) < 4:
        raise HTTPException(400, "密码至少 4 个字符")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "用户名已存在")
    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token(user.id)
    return {"token": token, "user": {"id": user.id, "username": user.username, "is_admin": user.is_admin}}


@router.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
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
