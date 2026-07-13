"""LLM 精选 Following 推文：偏好 AI/Agent/LLM，输出 keep/summary/score。"""
import json
import re
from openai import OpenAI

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_BATCH_SIZE = 40

_SYSTEM_PROMPT = """你是一位资深编辑，负责从 X（Twitter）关注流中精选值得放进个人早报「Following」板块的推文。

用户会给你一批推文（JSON 数组），每条有 tweet_id、handle、text。

请对每条输出评估结果，严格返回 JSON 数组，每个元素格式：
{"tweet_id": "<原始tweet_id>", "keep": <true或false>, "summary": "<一句话中文摘要>", "score": <0-100整数>}

精选偏好（优先 keep=true 且高分）：
- AI / Agent / LLM / 大模型相关的有信息量内容
- 产品发布、技术突破、开源项目、行业重要动态
- 有实质观点或可核对事实的长文/引用讨论

应 keep=false：
- 纯转发式无信息、广告、招聘、纯情绪发泄
- 与 AI/技术/行业无关的日常碎碎念
- 内容空洞、无法形成早报摘要的短帖

规则：
1. summary 必须基于原文，禁止编造
2. score 反映对 Following 板块读者的价值（AI/Agent/LLM 向加权）
3. 只返回 JSON 数组，不要任何解释文字
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


def _extract_json(text: str):
    """从 LLM 响应中提取 JSON，处理 markdown 代码块、NDJSON 和额外文本。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    lines = [line.strip() for line in text.strip().splitlines() if line.strip().startswith("{")]
    if lines:
        result = []
        for line in lines:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if result:
            return result
    return None


def _select_batch(items: list[dict]) -> list[dict]:
    """对一批推文调用 LLM，返回含 tweet_id/keep/summary/score 的列表。失败返回空列表。"""
    payload = json.dumps(items, ensure_ascii=False)
    try:
        resp = _get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        parsed = _extract_json(content)
        if parsed is None:
            logger.warning(f"无法从 LLM 响应中提取 JSON: {content[:200]}")
            return []
        if isinstance(parsed, list):
            return parsed
        for v in parsed.values():
            if isinstance(v, list):
                return v
        logger.warning("精选响应格式异常，无法解析为列表")
        return []
    except Exception as e:
        logger.warning(f"Following 精选失败（{len(items)} 条）: {e}")
        return []


def select_tweets(tweets: list[dict]) -> list[dict]:
    """
    批量 LLM 精选推文。
    过滤 keep=true，按 score 降序，截断至 settings.x_following_candidate_top_n。
    返回原推文字段 + summary/score。
    """
    if not tweets:
        return []

    by_id = {str(t["tweet_id"]): t for t in tweets}
    all_results: list[dict] = []

    for start in range(0, len(tweets), _BATCH_SIZE):
        batch = tweets[start : start + _BATCH_SIZE]
        items = [
            {
                "tweet_id": str(t["tweet_id"]),
                "handle": t.get("handle", ""),
                "text": (t.get("text") or "")[:500],
            }
            for t in batch
        ]
        all_results.extend(_select_batch(items))

    kept: list[dict] = []
    for r in all_results:
        if not isinstance(r, dict):
            continue
        if not r.get("keep", False):
            continue
        tid = str(r.get("tweet_id", ""))
        original = by_id.get(tid)
        if original is None:
            continue
        score = r.get("score", 0)
        if not isinstance(score, (int, float)):
            score = 0
        merged = {**original, "summary": r.get("summary", ""), "score": int(score)}
        kept.append(merged)

    kept.sort(key=lambda x: x.get("score", 0), reverse=True)
    top_n = settings.x_following_candidate_top_n
    return kept[:top_n]
