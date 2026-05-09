import json
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


_SYSTEM_PROMPT = """你是一位专业的科技新闻编辑。用户会给你一篇新闻的标题和正文，请输出严格的 JSON，不要有任何多余文字。

JSON 格式：
{
  "summary": "一句话摘要（30字以内，突出最核心事实）",
  "full_summary": "详细总结（100-200字，客观中立，涵盖关键事实、数据、影响）",
  "viewpoints": [
    {"view": "某方观点或影响判断", "source": "信息来源（公司/机构/人名，没有则留空）"}
  ],
  "background": "背景补充（50-100字，帮助读者理解事件的历史背景或行业背景）"
}

要求：
- 全部使用中文
- 观点列表 1-3 条，要标注来源
- 客观陈述，不加主观评价"""


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
        return json.loads(content)
    except Exception as e:
        logger.warning(f"摘要失败 [{title[:30]}]: {e}")
        return None


def summarize_and_save(db, articles: list, category: str = "ai") -> int:
    """对文章列表逐条摘要并写入 news_items，返回成功写入条数。"""
    from datetime import date
    from ..models import NewsItem

    today = date.today()
    saved = 0
    for art in articles:
        text = art.full_text or art.raw_summary or art.title
        result = summarize(art.title, text)
        if result is None:
            continue

        item = NewsItem(
            date=today,
            category=category,
            importance=50,
            title=art.title,
            summary=result.get("summary"),
            full_summary=result.get("full_summary"),
            viewpoints=result.get("viewpoints"),
            background=result.get("background"),
            source_links=[{"name": "36氪", "url": art.link}],
            raw_article_id=art.id,
        )
        db.add(item)
        saved += 1

    db.commit()
    logger.info(f"news_items 写入完成：{saved}/{len(articles)} 条")
    return saved
