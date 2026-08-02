"""llm 公共层回归测试：extract_json 解析矩阵 + chat_json 类型化重试。"""
import json
from unittest.mock import MagicMock

import httpx
import openai

from app.pipeline import llm


# ---------- extract_json ----------

class TestExtractJson:
    def test_plain_dict(self):
        assert llm.extract_json('{"a": 1}') == {"a": 1}

    def test_dict_mode_rejects_list(self):
        """历史修复：摘要若误收 list 会以异常结构写库，expect="dict" 永不返回 list。"""
        assert llm.extract_json("[1, 2, 3]", expect="dict") is None
        assert llm.extract_json('[{"a": 1}, {"b": 2}]', expect="dict") is None

    def test_dict_mode_single_object_list_unwraps_inner_dict(self):
        """回退链会截取文本中首个 {...} 片段：单元素对象数组被解包为该对象。
        返回类型仍是 dict 而非 list，不违反历史修复约束。"""
        result = llm.extract_json('[{"a": 1}]', expect="dict")
        assert result == {"a": 1}
        assert isinstance(result, dict)

    def test_list_mode_accepts_list(self):
        assert llm.extract_json('[{"a": 1}]', expect="list") == [{"a": 1}]

    def test_markdown_code_block(self):
        text = '结果如下：\n```json\n{"a": 1}\n```\n以上。'
        assert llm.extract_json(text) == {"a": 1}

    def test_json_embedded_in_text(self):
        text = '前置说明 {"a": 1, "b": {"c": 2}} 后置说明'
        assert llm.extract_json(text) == {"a": 1, "b": {"c": 2}}

    def test_garbage_returns_none(self):
        assert llm.extract_json("这不是 JSON") is None
        assert llm.extract_json("这不是 JSON", expect="list") is None

    def test_list_mode_unwraps_json_object_wrapper(self):
        text = json.dumps({"items": [{"id": 1}]})
        assert llm.extract_json(text, expect="list") == [{"id": 1}]

    def test_list_mode_wraps_single_object(self):
        assert llm.extract_json('{"id": 1}', expect="list") == [{"id": 1}]

    def test_list_mode_ndjson(self):
        text = '{"id": 1}\n{"id": 2}'
        assert llm.extract_json(text, expect="list") == [{"id": 1}, {"id": 2}]


# ---------- chat_json 重试 ----------

def _resp_with_content(
    content: str,
    *,
    finish_reason: str = "stop",
    completion_tokens: int = 10,
):
    resp = MagicMock()
    resp.choices = [MagicMock(
        message=MagicMock(content=content),
        finish_reason=finish_reason,
    )]
    resp.usage = MagicMock(completion_tokens=completion_tokens)
    return resp


def _rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://llm.test/v1/chat/completions")
    response = httpx.Response(429, request=request)
    return openai.RateLimitError("rate limited", response=response, body=None)


class TestChatJsonRetry:
    def test_logs_completion_metadata(self, monkeypatch, caplog):
        client = MagicMock()
        client.chat.completions.create.return_value = _resp_with_content(
            '{"ok": true}',
            finish_reason="length",
            completion_tokens=8192,
        )
        monkeypatch.setattr(llm, "get_client", lambda: client)

        result = llm.chat_json(
            [{"role": "user", "content": "return json"}],
            max_tokens=8192,
            log_tag="following_select",
        )

        assert result == {"ok": True}
        assert "finish_reason=length" in caplog.text
        assert "completion_tokens=8192" in caplog.text
        assert "max_tokens=8192" in caplog.text

    def test_disables_thinking_for_json_output(self, monkeypatch):
        client = MagicMock()
        client.chat.completions.create.return_value = _resp_with_content('{"ok": true}')
        monkeypatch.setattr(llm, "get_client", lambda: client)

        result = llm.chat_json([{"role": "user", "content": "return json"}])

        assert result == {"ok": True}
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["extra_body"] == {"thinking": {"type": "disabled"}}

    def test_rate_limit_retries_with_exponential_backoff(self, monkeypatch):
        calls = {"n": 0}

        def create(**_kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise _rate_limit_error()
            return _resp_with_content('{"ok": true}')

        client = MagicMock()
        client.chat.completions.create.side_effect = create
        monkeypatch.setattr(llm, "get_client", lambda: client)
        sleeps: list[float] = []
        monkeypatch.setattr(llm.time, "sleep", sleeps.append)

        result = llm.chat_json([{"role": "user", "content": "hi"}])

        assert result == {"ok": True}
        assert calls["n"] == 3
        assert sleeps == [2, 4]

    def test_rate_limit_exhausts_after_three_retries(self, monkeypatch):
        client = MagicMock()
        client.chat.completions.create.side_effect = _rate_limit_error()
        monkeypatch.setattr(llm, "get_client", lambda: client)
        sleeps: list[float] = []
        monkeypatch.setattr(llm.time, "sleep", sleeps.append)

        result = llm.chat_json([{"role": "user", "content": "hi"}])

        assert result is None
        assert client.chat.completions.create.call_count == 4  # 首次 + 3 次重试
        assert sleeps == [2, 4, 8]

    def test_non_rate_limit_error_does_not_retry(self, monkeypatch):
        client = MagicMock()
        client.chat.completions.create.side_effect = ValueError("boom")
        monkeypatch.setattr(llm, "get_client", lambda: client)
        sleeps: list[float] = []
        monkeypatch.setattr(llm.time, "sleep", sleeps.append)

        result = llm.chat_json([{"role": "user", "content": "hi"}])

        assert result is None
        assert client.chat.completions.create.call_count == 1
        assert sleeps == []
