"""规则过滤：丢弃纯转发与过短文本，保留原创与引用。"""
from app.pipeline.tweet_filter import filter_tweets


def _tweet(**overrides):
    base = {
        "tweet_id": "1",
        "handle": "someone",
        "text": "x" * 50,
        "is_retweet": False,
        "is_quote": False,
    }
    base.update(overrides)
    return base


def test_pure_retweet_dropped():
    tweets = [_tweet(tweet_id="rt", is_retweet=True, is_quote=False)]
    assert filter_tweets(tweets) == []


def test_quote_kept():
    tweets = [
        _tweet(
            tweet_id="q",
            is_retweet=False,
            is_quote=True,
            text="This is a quote with enough characters to pass.",
        )
    ]
    result = filter_tweets(tweets)
    assert len(result) == 1
    assert result[0]["tweet_id"] == "q"


def test_short_text_dropped():
    tweets = [_tweet(tweet_id="short", text="too short")]
    assert filter_tweets(tweets) == []


def test_long_original_kept():
    tweets = [
        _tweet(
            tweet_id="orig",
            text="A substantial original tweet about AI agents and LLM tooling.",
        )
    ]
    result = filter_tweets(tweets)
    assert len(result) == 1
    assert result[0]["tweet_id"] == "orig"
