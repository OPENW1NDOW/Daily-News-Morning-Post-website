"""
批量分类与重要度评分。
每次最多 40 条，输出每条的 {category, importance, keep}。
"""
import json
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

_SYSTEM_PROMPT = f"""你是一位科技新闻分类编辑。用户会给你一批新闻条目（JSON 数组），每条有 id、title、summary。

请对每条输出分类结果，严格返回 JSON 数组，每个元素格式：
{{"id": <原始id>, "category": "<板块key>", "importance": <0-100整数>, "keep": <true或false>}}

板块说明：
{_CATEGORY_DESC.strip()}

规则：
1. category 必须是上面 10 个 key 之一，或 "other"（明显不相关时才用 other）
2. importance 反映新闻的重要程度：重大突破/重要政策/头部公司大动作 80-100，普通资讯 30-60，软文/低质 0-30
3. keep=false 的情况：明显广告、软文、招聘、活动预告、与科技/AI/经济完全无关
4. 每条只归入相关度最高的单一板块
5. 只返回 JSON 数组，不要任何解释文字"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    return _client


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
        parsed = json.loads(content)
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
