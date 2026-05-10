"""
批量分类与重要度评分。
每次最多 40 条，输出每条的 {category, importance, keep}。
"""
import json
import re
from openai import OpenAI
from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_BATCH_SIZE = 40

CATEGORIES = [
    "ai", "tech", "policy", "research",
    "business", "international", "chip",
    "robotics", "security", "social",
]

_CATEGORY_DESC = """
- ai: 大语言模型、多模态、AI产品、算法突破、开源模型
- tech: 科技公司动态、产品发布、行业竞争、投融资
- policy: AI法规、数据安全、政府政策、国际监管
- research: 论文、实验室成果、基础科学突破
- business: 宏观经济、商业模式、企业战略、市场分析
- international: 地缘政治、国际关系、重大外交事件
- chip: 半导体、GPU、CPU、硬件创新、供应链
- robotics: 具身智能、工业机器人、自动驾驶
- security: 数据泄露、漏洞、攻防、隐私保护
- social: AI对就业/教育/伦理/社会结构的影响
"""

_SYSTEM_PROMPT = f"""你是一位资深新闻编辑，负责新闻的分类与价值评估。用户会给你一批新闻条目（JSON 数组），每条有 id、title、summary。

请对每条输出分类结果，严格返回 JSON 数组，每个元素格式：
{{"id": <原始id>, "category": "<板块key>", "importance": <0-100整数>, "keep": <true或false>}}

板块说明：
{_CATEGORY_DESC.strip()}

分类规则：
1. category 必须是上面 10 个 key 之一，或 "other"（明显不相关时才用 other）
2. 每条只归入相关度最高的单一板块

重要性评估标准（importance）：
- 80-100：重大突发事件、影响深远的政策法规、行业格局性事件
- 50-79：有实质价值的行业动态、值得关注的技术进展、重要企业决策
- 30-49：常规资讯、一般性报道
- 0-29：软文、低质内容、缺乏信息增量的文章

过滤标准（keep=false）：
- 明显广告、软文、招聘、活动预告
- 标题党但内容空洞
- 重复报道同一事件且无新增信息

只返回 JSON 数组，不要任何解释文字"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


def _extract_json(text: str):
    """从 LLM 响应中提取 JSON，处理 markdown 代码块、NDJSON 和额外文本。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 提取 markdown 代码块中的 JSON
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 提取第一个 [ ... ]
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # NDJSON：每行一个 JSON 对象
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


def _classify_batch(items: list[dict]) -> list[dict]:
    """对一批条目（含 id/title/summary）调用 LLM，返回分类结果列表。失败返回空列表。"""
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
        # 部分模型 json_object 模式可能把数组包在某个 key 下
        if isinstance(parsed, list):
            return parsed
        # 尝试找第一个 list 值
        for v in parsed.values():
            if isinstance(v, list):
                return v
        logger.warning("分类响应格式异常，无法解析为列表")
        return []
    except Exception as e:
        logger.warning(f"批量分类失败（{len(items)} 条）: {e}")
        return []


def classify_articles(db, articles: list) -> int:
    """
    对 raw_articles 列表批量分类，更新 category/importance 字段。
    返回成功分类的条数。
    """
    total_classified = 0

    for batch_start in range(0, len(articles), _BATCH_SIZE):
        batch = articles[batch_start: batch_start + _BATCH_SIZE]
        items = [
            {
                "id": art.id,
                "title": art.title,
                "summary": (art.raw_summary or "")[:200],
            }
            for art in batch
        ]

        results = _classify_batch(items)
        if not results:
            logger.warning(f"批次 {batch_start}-{batch_start+len(batch)} 分类失败，跳过")
            continue

        # 建立 id → result 映射
        result_map = {r["id"]: r for r in results if isinstance(r, dict) and "id" in r}

        for art in batch:
            r = result_map.get(art.id)
            if r is None:
                continue
            cat = r.get("category", "other")
            imp = r.get("importance", 50)
            keep = r.get("keep", True)

            if cat not in CATEGORIES:
                cat = "other"
            if not isinstance(imp, int) or not (0 <= imp <= 100):
                imp = 50

            art.category = cat if keep else "other"
            art.importance = imp
            total_classified += 1

        db.commit()
        logger.info(f"分类批次 {batch_start//40 + 1}：{len(results)} 条完成")

    logger.info(f"全部分类完成：{total_classified}/{len(articles)} 条")
    return total_classified
