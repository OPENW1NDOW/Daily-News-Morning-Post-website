"""LLM 公共层：客户端单例、JSON 提取、带类型化异常重试的 chat 调用。"""
import json
import re
import threading
import time

import openai
from openai import OpenAI

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 120

_RATE_LIMIT_RETRIES = 3  # 429：指数退避 2s/4s/8s
_TRANSIENT_RETRIES = 1   # 连接/超时/服务端 5xx：重试 1 次

_client: OpenAI | None = None
_client_lock = threading.Lock()


def get_client() -> OpenAI:
    """懒加载单例客户端（OpenAI SDK 客户端线程安全，可跨线程共享）。"""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


def _parse_candidates(text: str, expect: str):
    """按优先级产出候选解析结果：整体解析 → markdown 代码块 → 首个 JSON 片段 → NDJSON。"""
    try:
        yield json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            yield json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    pattern = r"\[.*\]" if expect == "list" else r"\{.*\}"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        try:
            yield json.loads(m.group())
        except json.JSONDecodeError:
            pass
    if expect == "list":
        rows = []
        for line in text.strip().splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if rows:
            yield rows


def extract_json(text: str, expect: str = "dict") -> dict | list | None:
    """
    从 LLM 响应中提取 JSON，处理 markdown 代码块、NDJSON 和额外文本。
    expect="dict"：只接受 JSON 对象，列表输入返回 None
        （保留历史修复：摘要若误收 list 会以异常结构写库）。
    expect="list"：接受数组；对象输入取其第一个 list 值
        （json_object 模式常把数组包在某个 key 下），否则视为单元素列表。
    """
    for parsed in _parse_candidates(text, expect):
        if expect == "dict":
            if isinstance(parsed, dict):
                return parsed
            continue
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
            return [parsed]
    return None


def chat_json(
    messages: list[dict],
    *,
    temperature: float = 0.1,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float = DEFAULT_TIMEOUT,
    expect: str = "dict",
    log_tag: str = "",
) -> dict | list | None:
    """
    调用 LLM 并按 expect 提取 JSON，失败返回 None。
    重试策略：RateLimitError 指数退避重试 3 次（2s/4s/8s）；
    APIConnectionError/APITimeoutError/InternalServerError 重试 1 次；其他异常不重试。
    """
    tag = f"[{log_tag}] " if log_tag else ""
    rate_limit_left = _RATE_LIMIT_RETRIES
    transient_left = _TRANSIENT_RETRIES
    while True:
        try:
            resp = get_client().chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = resp.choices[0].message.content or ""
            result = extract_json(content, expect=expect)
            if result is None:
                logger.warning(f"{tag}无法从 LLM 响应中提取 JSON: {content[:200]}")
            return result
        except openai.RateLimitError as e:
            if rate_limit_left <= 0:
                logger.warning(f"{tag}LLM 限流重试耗尽: {e}")
                return None
            wait = 2 ** (_RATE_LIMIT_RETRIES - rate_limit_left + 1)
            rate_limit_left -= 1
            logger.info(f"{tag}LLM 限流，{wait}s 后重试")
            time.sleep(wait)
        except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
            if transient_left <= 0:
                logger.warning(f"{tag}LLM 调用失败（连接/超时/服务端错误）: {e}")
                return None
            transient_left -= 1
            logger.info(f"{tag}LLM 瞬时错误，1s 后重试: {e}")
            time.sleep(1)
        except Exception as e:
            logger.warning(f"{tag}LLM 调用失败: {e}")
            return None
