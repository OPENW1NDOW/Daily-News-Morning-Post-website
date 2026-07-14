"""bird_client：subprocess 可 mock，Cookie 缺失即失败。"""
import json
import subprocess

import pytest

from app.config import settings


def test_missing_cookie_raises_before_subprocess(monkeypatch):
    from app.pipeline import bird_client

    monkeypatch.setattr(settings, "x_auth_token", "")
    monkeypatch.setattr(settings, "x_ct0", "ct0-value")
    called = []

    def fake_run(*args, **kwargs):
        called.append((args, kwargs))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr(bird_client.subprocess, "run", fake_run)

    with pytest.raises(bird_client.BirdAuthError):
        bird_client.list_following()

    assert called == []


def test_list_following_invokes_bird_and_normalizes(monkeypatch):
    from app.pipeline import bird_client

    monkeypatch.setattr(settings, "x_auth_token", "auth-token")
    monkeypatch.setattr(settings, "x_ct0", "ct0-token")
    monkeypatch.setattr(settings, "bird_bin", "bird-bin")

    payload = [
        {
            "id": "111",
            "username": "alice",
            "name": "Alice",
            "profileImageUrl": "https://img/a.jpg",
        },
        {
            "id_str": "222",
            "screen_name": "bob",
            "name": "Bob",
        },
    ]
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(bird_client.subprocess, "run", fake_run)

    result = bird_client.list_following()

    assert captured["argv"][0] == "bird-bin"
    assert "following" in captured["argv"]
    assert "--json" in captured["argv"]
    assert captured["env"]["AUTH_TOKEN"] == "auth-token"
    assert captured["env"]["CT0"] == "ct0-token"
    assert captured["env"]["NODE_USE_ENV_PROXY"] == "1"
    assert captured["env"]["HTTP_PROXY"] == settings.proxy_url
    assert captured["env"]["HTTPS_PROXY"] == settings.proxy_url
    assert captured["env"]["ALL_PROXY"] == settings.proxy_url
    assert result == [
        {
            "x_user_id": "111",
            "handle": "alice",
            "display_name": "Alice",
            "avatar_url": "https://img/a.jpg",
        },
        {
            "x_user_id": "222",
            "handle": "bob",
            "display_name": "Bob",
            "avatar_url": None,
        },
    ]


def test_fetch_user_tweets_filters_by_date_window(monkeypatch):
    from app.pipeline import bird_client

    monkeypatch.setattr(settings, "x_auth_token", "auth-token")
    monkeypatch.setattr(settings, "x_ct0", "ct0-token")
    monkeypatch.setattr(settings, "bird_bin", "bird")

    payload = {
        "tweets": [
            {
                "id": "1",
                "text": "too early",
                "createdAt": "2026-07-12T23:59:59+00:00",
                "author": {"username": "alice"},
            },
            {
                "id": "2",
                "full_text": "in window original",
                "created_at": "2026-07-13T08:00:00+00:00",
                "author": {"username": "alice", "name": "Alice"},
            },
            {
                "id_str": "3",
                "text": "quote tweet",
                "createdAt": "2026-07-13T12:00:00Z",
                "username": "alice",
                "quotedTweet": {"id": "99", "text": "orig"},
            },
            {
                "id": "4",
                "text": "retweet",
                "createdAt": "2026-07-13T15:00:00+00:00",
                "author": {"username": "alice"},
                "retweeted_status": {"id": "88"},
            },
            {
                "id": "5",
                "text": "until exclusive",
                "createdAt": "2026-07-14T00:00:00+00:00",
                "author": {"username": "alice"},
            },
        ]
    }
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(bird_client.subprocess, "run", fake_run)

    result = bird_client.fetch_user_tweets(
        "alice",
        since_iso="2026-07-13T00:00:00+00:00",
        until_iso="2026-07-14T00:00:00+00:00",
    )

    assert "user-tweets" in captured["argv"]
    assert "@alice" in captured["argv"] or "alice" in captured["argv"]
    assert "--json" in captured["argv"]
    assert [t["tweet_id"] for t in result] == ["2", "3", "4"]
    assert result[0] == {
        "tweet_id": "2",
        "handle": "alice",
        "text": "in window original",
        "created_at": "2026-07-13T08:00:00+00:00",
        "is_retweet": False,
        "is_quote": False,
    }
    assert result[1]["is_quote"] is True
    assert result[1]["is_retweet"] is False
    assert result[2]["is_retweet"] is True
    assert result[2]["is_quote"] is False


def test_fetch_user_tweets_parses_twitter_created_at(monkeypatch):
    """bird 实际返回 Twitter 经典时间串，不能静默丢弃。"""
    from app.pipeline import bird_client

    monkeypatch.setattr(settings, "x_auth_token", "auth-token")
    monkeypatch.setattr(settings, "x_ct0", "ct0-token")
    monkeypatch.setattr(settings, "bird_bin", "bird")

    payload = {
        "tweets": [
            {
                "id": "10",
                "text": "before window",
                "createdAt": "Sun Jul 12 15:59:59 +0000 2026",
                "author": {"username": "alice"},
            },
            {
                "id": "11",
                "text": "in window via twitter date",
                "createdAt": "Mon Jul 13 16:00:00 +0000 2026",
                "author": {"username": "alice"},
            },
            {
                "id": "12",
                "text": "after window",
                "createdAt": "Tue Jul 14 00:00:00 +0000 2026",
                "author": {"username": "alice"},
            },
        ]
    }

    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(
            args=argv, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    monkeypatch.setattr(bird_client.subprocess, "run", fake_run)

    result = bird_client.fetch_user_tweets(
        "alice",
        since_iso="2026-07-13T00:00:00+00:00",
        until_iso="2026-07-14T00:00:00+00:00",
    )

    assert [t["tweet_id"] for t in result] == ["11"]
    assert result[0]["created_at"] == "Mon Jul 13 16:00:00 +0000 2026"
