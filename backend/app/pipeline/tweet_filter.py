"""规则过滤推文：去掉纯转发与过短文本。"""


def filter_tweets(tweets: list[dict], *, min_chars: int = 40) -> list[dict]:
    """丢弃纯转发与过短文本，保留原创与 quote。"""
    kept = []
    for t in tweets:
        if t.get("is_retweet") and not t.get("is_quote"):
            continue
        text = (t.get("text") or "").strip()
        if len(text) < min_chars:
            continue
        kept.append(t)
    return kept
