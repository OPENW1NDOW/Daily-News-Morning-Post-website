"""LLM 精选 Following 推文：mock OpenAI，验证 keep/score 排序与截断。"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.pipeline import following_select as mod


def _tweet(tweet_id: str, text: str = "A long enough tweet about AI agents and tools."):
    return {
        "tweet_id": tweet_id,
        "handle": "ai_person",
        "text": text,
        "link": f"https://x.com/i/status/{tweet_id}",
        "published_at": "2026-07-13T10:00:00+00:00",
        "is_retweet": False,
        "is_quote": False,
    }


def _mock_client(content: str) -> MagicMock:
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_client.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    return mock_client


def test_keeps_and_sorts_by_score_desc(monkeypatch):
    tweets = [_tweet("a"), _tweet("b"), _tweet("c")]
    payload = json.dumps([
        {"tweet_id": "a", "keep": True, "summary": "低分", "score": 40},
        {"tweet_id": "b", "keep": True, "summary": "高分", "score": 90},
        {"tweet_id": "c", "keep": False, "summary": "丢弃", "score": 99},
    ])
    mock_client = _mock_client(payload)
    monkeypatch.setattr(mod, "_get_client", lambda: mock_client)

    result = mod.select_tweets(tweets)

    assert [r["tweet_id"] for r in result] == ["b", "a"]
    assert result[0]["summary"] == "高分"
    assert result[0]["score"] == 90
    assert result[0]["handle"] == "ai_person"
    assert result[0]["text"].startswith("A long enough")


def test_truncates_to_top_n(monkeypatch):
    tweets = [_tweet(str(i)) for i in range(10)]
    items = [
        {"tweet_id": str(i), "keep": True, "summary": f"s{i}", "score": i * 10}
        for i in range(10)
    ]
    mock_client = _mock_client(json.dumps(items))
    monkeypatch.setattr(mod, "_get_client", lambda: mock_client)
    monkeypatch.setattr(mod.settings, "x_following_candidate_top_n", 8)

    result = mod.select_tweets(tweets)

    assert len(result) == 8
    assert result[0]["tweet_id"] == "9"
    assert result[-1]["tweet_id"] == "2"


def test_temperature_is_low(monkeypatch):
    tweets = [_tweet("1")]
    payload = json.dumps([
        {"tweet_id": "1", "keep": True, "summary": "ok", "score": 80},
    ])
    mock_client = _mock_client(payload)
    monkeypatch.setattr(mod, "_get_client", lambda: mock_client)

    mod.select_tweets(tweets)

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["temperature"] == 0.1


def test_empty_input_returns_empty(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(mod, "_get_client", lambda: mock_client)
    assert mod.select_tweets([]) == []
    mock_client.chat.completions.create.assert_not_called()


def test_api_error_raises(monkeypatch):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API timeout")
    monkeypatch.setattr(mod, "_get_client", lambda: mock_client)

    with pytest.raises(Exception, match="API timeout"):
        mod.select_tweets([_tweet("1")])
