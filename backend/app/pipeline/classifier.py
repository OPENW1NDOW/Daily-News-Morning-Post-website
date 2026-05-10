"""
批量分类与重要度评分。
每次最多 40 条，输出每条的 {category, importance, keep}。
各板块有独立的分类标准，由 CATEGORY_CRITERIA 定义。
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
    "ai", "tech", "internet", "finance", "business",
    "international", "ai_paper", "social",
]

# ── 各板块独立的分类标准 ─────────────────────────────────────
CATEGORY_CRITERIA = {
    "ai": {
        "name": "AI 与大模型",
        "focus": "大语言模型、多模态AI、AI产品发布、算法突破、开源模型、AI公司融资与战略",
        "importance_high": "GPT级别模型发布、重大算法突破、头部AI公司战略级动作",
        "importance_mid": "AI产品更新、开源模型发布、AI应用落地案例",
        "reject": "泛科技新闻（非AI核心）、AI概念炒作但无实质内容",
    },
    "tech": {
        "name": "科技产业",
        "focus": "消费电子产品、硬件设备、软件应用、技术趋势、开发者生态",
        "importance_high": "新品类发布（如Vision Pro级别）、颠覆性技术变革",
        "importance_mid": "产品迭代更新、硬件评测、技术教程",
        "reject": "互联网平台运营、AI相关（应归ai板块）、金融数据",
    },
    "internet": {
        "name": "互联网",
        "focus": "互联网公司动态、平台运营策略、社交网络、电商、游戏、内容生态、用户增长",
        "importance_high": "巨头战略转型、重大并购、监管政策影响整个行业",
        "importance_mid": "产品功能更新、运营策略变化、行业数据分析",
        "reject": "纯技术论文、硬件产品、金融投资数据",
    },
    "finance": {
        "name": "金融投资",
        "focus": "股市行情、投资机构动向、宏观经济政策对市场影响、加密货币、企业IPO与融资",
        "importance_high": "市场重大波动、央行政策、百亿级并购/IPO",
        "importance_mid": "个股异动、机构调仓、行业融资事件",
        "reject": "纯商业分析（无金融数据支撑）、科技产品新闻",
    },
    "business": {
        "name": "商业与经济",
        "focus": "企业战略、商业模式创新、产业格局变化、就业市场、消费趋势、宏观经济",
        "importance_high": "行业格局重塑、重大企业战略转型、全球经济事件",
        "importance_mid": "企业财报、行业报告、商业模式分析",
        "reject": "纯金融交易数据（应归finance）、科技产品发布",
    },
    "international": {
        "name": "国际时政",
        "focus": "地缘政治、国际关系、重大外交事件、战争冲突、全球治理、国际组织",
        "importance_high": "战争/和平进程、重大外交突破、国际制裁",
        "importance_mid": "国家间摩擦、国际会议、政策声明",
        "reject": "科技公司海外业务（应归tech/internet）、经济制裁的具体金融影响",
    },
    "ai_paper": {
        "name": "AI 前沿论文",
        "focus": "AI领域最新学术论文、实验室突破、技术创新、算法进展、学术会议",
        "importance_high": "顶会最佳论文、颠覆性算法、Nature/Science级AI成果",
        "importance_mid": "arXiv热门论文、知名实验室成果、技术报告",
        "reject": "AI产品商业新闻（应归ai）、科普文章、综述类内容",
    },
    "social": {
        "name": "社会人文",
        "focus": "社会热点事件、民生问题、文化现象、教育变革、伦理讨论、环境保护、公共健康",
        "importance_high": "重大社会事件、影响广泛的政策变化、公共卫生危机",
        "importance_mid": "社会现象讨论、教育改革、文化趋势",
        "reject": "科技产品新闻、金融市场数据、纯学术论文",
    },
}

_CATEGORY_DESC = "\n".join(
    f"- {k}: {v['focus']}" for k, v in CATEGORY_CRITERIA.items()
)

_SYSTEM_PROMPT = f"""你是一位资深新闻编辑，负责新闻的分类与价值评估。用户会给你一批新闻条目（JSON 数组），每条有 id、title、summary。

请对每条输出分类结果，严格返回 JSON 数组，每个元素格式：
{{"id": <原始id>, "category": "<板块key>", "importance": <0-100整数>, "keep": <true或false>}}

板块分类标准：
{_CATEGORY_DESC}

重要性评估规则：
每条新闻根据其所属板块的具体标准评估重要性：
""" + "\n".join(
    f"""【{v['name']}】
  - 高（80-100）：{v['importance_high']}
  - 中（50-79）：{v['importance_mid']}
  - 低（0-49）：常规资讯、一般性报道"""
    for v in CATEGORY_CRITERIA.values()
) + """

过滤规则（keep=false）：
- 明显广告、软文、招聘、活动预告
- 标题党但内容空洞
- 重复报道同一事件且无新增信息
""" + "\n".join(
    f"- 【{v['name']}】排除：{v['reject']}"
    for v in CATEGORY_CRITERIA.values()
) + """

分类核心原则：
1. category 必须是上面 8 个 key 之一，或 "other"（明显不相关时才用 other）
2. 每条只归入相关度最高的单一板块
3. 严格基于标题和摘要内容判断，不要推测文章未提及的信息

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
