import json
import re
from openai import OpenAI
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


_SYSTEM_PROMPT = """你是一位专业新闻编辑，负责对新闻进行摘要、总结和观点提炼。用户会给你一篇新闻的标题和正文，请输出严格的 JSON，不要有任何多余文字。

JSON 格式：
{
  "summary": "一句话摘要（30字以内，突出最核心事实）",
  "full_summary": "详细总结（100-200字，客观中立，涵盖关键事实、数据、影响）",
  "viewpoints": [
    {"view": "某方观点或影响判断", "source": "信息来源（公司/机构/人名，没有则留空）"}
  ],
  "background": "背景补充（50-100字，帮助读者理解事件的历史背景或行业背景）"
}

核心原则——真实性是新闻的生命线：
1. 所有内容必须严格基于原文，禁止编造、杜撰、推测任何信息
2. 原文没有提到的年份、数字、人名、事件、数据，绝对不能自行添加
3. 如果原文信息不足以支撑某个字段（如背景），宁可留空也不要虚构
4. 摘要和总结中涉及的每一个事实、数字、日期，都必须能在原文中找到依据

在此基础上，追求新闻价值：
- 观点列表 1-3 条，要标注来源
- 背景补充要基于原文提供的线索，或广为人知的客观事实
- 客观陈述，不加主观评价
- 全部使用中文"""


def _extract_json(text: str):
    """从 LLM 响应中提取 JSON，处理 markdown 代码块和额外文本。"""
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
    for pattern in [r"\[.*\]", r"\{.*\}"]:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
    return None


def summarize(title: str, text: str) -> dict | None:
    """对单篇文章生成摘要，失败返回 None。"""
    prompt = f"标题：{title}\n\n正文：{text[:3000]}"
    try:
        resp = _get_client().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        result = _extract_json(content)
        if result is None:
            logger.warning(f"无法从摘要响应中提取 JSON [{title[:30]}]: {content[:200]}")
        return result
    except Exception as e:
        logger.warning(f"摘要失败 [{title[:30]}]: {e}")
        return None


