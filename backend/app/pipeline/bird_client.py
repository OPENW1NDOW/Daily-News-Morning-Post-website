"""bird CLI wrapper for X following list and user tweets."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings

_FOLLOWING_TIMEOUT_S = 120
_TWEETS_TIMEOUT_S = 90
_USER_TWEETS_COUNT = 40


class BirdAuthError(Exception):
    """Raised when X cookie credentials are missing."""


def _require_auth() -> None:
    if not (settings.x_auth_token or "").strip() or not (settings.x_ct0 or "").strip():
        raise BirdAuthError("missing x_auth_token or x_ct0")


def _resolve_bird_bin() -> str:
    """解析 bird 可执行文件。uvicorn PATH 常不含 npm 全局目录。"""
    configured = (settings.bird_bin or "bird").strip() or "bird"
    if os.path.isfile(configured):
        return configured
    found = shutil.which(configured)
    if found:
        return found
    # Windows：npm -g 装的 bird.cmd 常在 %APPDATA%\npm，但后端进程 PATH 没有它
    if os.name == "nt" and Path(configured).name in ("bird", "bird.cmd", "bird.ps1"):
        npm_dir = Path(os.environ.get("APPDATA", "")) / "npm"
        for name in ("bird.cmd", "bird.exe", "bird"):
            candidate = npm_dir / name
            if candidate.is_file():
                return str(candidate)
    return configured


def _auth_env() -> dict[str, str]:
    """注入 Cookie + 代理。Node fetch 默认不读 HTTP(S)_PROXY，须 NODE_USE_ENV_PROXY=1。"""
    env = os.environ.copy()
    env["AUTH_TOKEN"] = settings.x_auth_token
    env["CT0"] = settings.x_ct0
    # 浏览器能上 x.com ≠ Node/bird 能连；国内代理场景必开
    env["NODE_USE_ENV_PROXY"] = "1"
    proxy = (settings.proxy_url or "").strip()
    if proxy:
        env["HTTP_PROXY"] = proxy
        env["HTTPS_PROXY"] = proxy
        env["ALL_PROXY"] = proxy
    # 确保子进程也能找到 npm 全局 bin（bird.cmd 会再调 node）
    npm_bin = str(Path(os.environ.get("APPDATA", "")) / "npm")
    path = env.get("PATH", "")
    if npm_bin and npm_bin not in path:
        env["PATH"] = npm_bin + os.pathsep + path
    return env


def _run_bird(args: list[str], *, timeout: int) -> Any:
    _require_auth()
    bird_bin = _resolve_bird_bin()
    try:
        completed = subprocess.run(
            [bird_bin, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_auth_env(),
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            f"bird executable not found ({bird_bin!r}). "
            "Install @steipete/bird globally or set BIRD_BIN to absolute path of bird.cmd"
        ) from e
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        # stderr 可能回显环境中的 Cookie 凭证，拼进异常前先脱敏并截断
        for secret in (settings.x_auth_token, settings.x_ct0):
            secret = (secret or "").strip()
            if secret:
                err = err.replace(secret, "****")
        raise RuntimeError(f"bird failed ({completed.returncode}): {err[:500]}")
    stdout = (completed.stdout or "").strip()
    if not stdout:
        return []
    return json.loads(stdout)


def _as_list(payload: Any, *keys: str) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
        # Single user/tweet object
        if any(k in payload for k in ("id", "id_str", "username", "screen_name", "text", "full_text")):
            return [payload]
    return []


def _first_str(obj: dict, *keys: str) -> str | None:
    for key in keys:
        value = obj.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_user(raw: dict) -> dict:
    avatar = _first_str(
        raw,
        "profileImageUrl",
        "profile_image_url",
        "avatar_url",
        "profile_image_url_https",
    )
    return {
        "x_user_id": _first_str(raw, "id", "id_str", "userId", "user_id") or "",
        "handle": _first_str(raw, "username", "screen_name", "handle") or "",
        "display_name": _first_str(raw, "name", "display_name", "displayName") or "",
        "avatar_url": avatar,
    }


def list_following() -> list[dict]:
    """Return normalized following accounts via `bird following --json --all`."""
    payload = _run_bird(["following", "--json", "--all"], timeout=_FOLLOWING_TIMEOUT_S)
    users = _as_list(payload, "users", "following", "data")
    return [_normalize_user(u) for u in users]


# bird/X 常用两种时间：ISO8601，或 Twitter 经典 "Mon Jul 13 13:42:15 +0000 2026"
_TWITTER_CREATED_AT = "%a %b %d %H:%M:%S %z %Y"


def _parse_dt(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        dt = datetime.strptime(text, _TWITTER_CREATED_AT)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_retweet(raw: dict) -> bool:
    if raw.get("isRetweet") is True or raw.get("is_retweet") is True:
        return True
    if raw.get("retweeted_status") or raw.get("retweetedStatus"):
        return True
    text = _first_str(raw, "full_text", "text", "fullText") or ""
    return text.startswith("RT @")


def _is_quote(raw: dict) -> bool:
    if raw.get("isQuote") is True or raw.get("is_quote") is True:
        return True
    return bool(raw.get("quoted_status") or raw.get("quotedTweet") or raw.get("quoted_status_id_str"))


def _tweet_handle(raw: dict, fallback: str) -> str:
    author = raw.get("author")
    if isinstance(author, dict):
        handle = _first_str(author, "username", "screen_name", "handle")
        if handle:
            return handle
    return _first_str(raw, "username", "screen_name", "handle") or fallback


def _normalize_tweet(raw: dict, handle: str) -> dict:
    created = _first_str(raw, "createdAt", "created_at", "created") or ""
    return {
        "tweet_id": _first_str(raw, "id", "id_str", "tweet_id") or "",
        "handle": _tweet_handle(raw, handle),
        "text": _first_str(raw, "full_text", "text", "fullText") or "",
        "created_at": created,
        "is_retweet": _is_retweet(raw),
        "is_quote": _is_quote(raw),
    }


def _normalize_handle(handle: str) -> str:
    h = handle.strip()
    if not h:
        return h
    return h if h.startswith("@") else f"@{h}"


def fetch_user_tweets(handle: str, since_iso: str, until_iso: str) -> list[dict]:
    """Fetch tweets then keep those in [since_iso, until_iso)."""
    user = _normalize_handle(handle)
    bare = user.lstrip("@")
    payload = _run_bird(
        ["user-tweets", user, "-n", str(_USER_TWEETS_COUNT), "--json"],
        timeout=_TWEETS_TIMEOUT_S,
    )
    tweets = _as_list(payload, "tweets", "data")
    since = _parse_dt(since_iso)
    until = _parse_dt(until_iso)
    out: list[dict] = []
    for raw in tweets:
        item = _normalize_tweet(raw, bare)
        if not item["created_at"]:
            continue
        try:
            created = _parse_dt(item["created_at"])
        except ValueError:
            continue
        if since <= created < until:
            out.append(item)
    return out
