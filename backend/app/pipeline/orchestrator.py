"""
流水线编排：7 步完整流程。
fetch → time_filter → classify → select_top → extract → summarize → persist
"""
import asyncio
from datetime import datetime, date, timedelta, timezone
from ..utils.logger import get_logger
from .classifier import CATEGORIES

logger = get_logger(__name__)

TOP_PER_CATEGORY = 8   # 每板块取 top-8 进入摘要，保留 6 条
FINAL_PER_CATEGORY = 6
LOOKBACK_HOURS = 24

# 流水线进度（供 admin status API 轮询）
_pipeline_progress: dict = {
    "running": False,
    "step": "",
    "step_index": 0,
    "total_steps": 7,
    "categories_done": 0,
    "total_categories": 10,
}


def get_pipeline_progress() -> dict:
    return dict(_pipeline_progress)


def run_daily(db) -> dict:
    """
    同步入口，供 scheduler / admin API 调用。
    返回每板块最终写入条数的汇总 dict。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_run_daily_async(db))
    finally:
        loop.close()


async def _run_daily_async(db) -> dict:
    from ..models import Source, RawArticle, NewsItem
    from .fetcher import fetch_and_save_all_async
    from .classifier import classify_articles
    from .extractor import extract_text
    from .summarizer import summarize

    today = date.today()
    logger.info(f"===== 流水线开始：{today} =====")
    _pipeline_progress["running"] = True
    _pipeline_progress["categories_done"] = 0

    try:
        # ── Step 1: 拉取所有启用源 ─────────────────────────────
        _pipeline_progress["step"] = "正在拉取 RSS 源..."
        _pipeline_progress["step_index"] = 1
        logger.info("[1/7] 拉取 RSS 源...")
        sources = db.query(Source).filter_by(enabled=True).all()
        fetch_counts = await fetch_and_save_all_async(db, sources)
        total_fetched = sum(fetch_counts.values())
        logger.info(f"[1/7] 共拉取 {total_fetched} 条新原始文章")

        # ── Step 2: 过滤 24h 内的文章 ──────────────────────────
        _pipeline_progress["step"] = "正在筛选 24h 内文章..."
        _pipeline_progress["step_index"] = 2
        logger.info("[2/7] 过滤 24h 内文章...")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
        candidates = db.query(RawArticle).filter(
            (RawArticle.published_at >= cutoff) | (RawArticle.published_at.is_(None))
        ).all()
        logger.info(f"[2/7] 候选文章：{len(candidates)} 条")

        if not candidates:
            logger.warning("无候选文章，流水线结束")
            return {}

        # ── Step 3: AI 分类 + 重要度 ───────────────────────────
        _pipeline_progress["step"] = "AI 正在分类与评分..."
        _pipeline_progress["step_index"] = 3
        logger.info("[3/7] AI 分类与重要度评分...")
        classify_articles(db, candidates)
        db.refresh

        # ── Step 4: 每板块按 importance 取 top-8 ─────────────
        _pipeline_progress["step"] = "正在筛选每个板块的候选..."
        _pipeline_progress["step_index"] = 4
        logger.info("[4/7] 按板块筛选 top-8...")
        category_pools: dict[str, list] = {cat: [] for cat in CATEGORIES}
        for art in candidates:
            if art.category in CATEGORIES:
                category_pools[art.category].append(art)

        for cat in CATEGORIES:
            category_pools[cat].sort(key=lambda a: (a.importance or 0), reverse=True)
            category_pools[cat] = category_pools[cat][:TOP_PER_CATEGORY]
            logger.info(f"  {cat}: {len(category_pools[cat])} 条候选")

        # ── Step 5: 提取正文 ────────────────────────────────────
        _pipeline_progress["step"] = "正在提取新闻正文..."
        _pipeline_progress["step_index"] = 5
        logger.info("[5/7] 正文提取...")
        all_selected = [art for pool in category_pools.values() for art in pool]
        for art in all_selected:
            if art.full_text:
                continue
            src = db.query(Source).get(art.source_id)
            use_proxy = src.use_proxy if src else False
            text = extract_text(art.link, use_proxy=use_proxy)
            art.full_text = text or art.raw_summary or art.title
        db.commit()
        logger.info(f"[5/7] 正文提取完成（共 {len(all_selected)} 篇）")

        # ── Step 6: 生成摘要 ────────────────────────────────────
        _pipeline_progress["step"] = "AI 正在生成摘要..."
        _pipeline_progress["step_index"] = 6
        logger.info("[6/7] 生成 AI 摘要...")
        summary_results: dict[int, dict | None] = {}
        for art in all_selected:
            text = art.full_text or art.raw_summary or art.title
            result = summarize(art.title, text)
            summary_results[art.id] = result
            status = "ok" if result else "fail"
            logger.debug(f"  摘要 [{status}] {art.title[:40]}")

        # ── Step 7: 写入 news_items ──────────────────────────────
        _pipeline_progress["step"] = "正在写入结果..."
        _pipeline_progress["step_index"] = 7
        logger.info("[7/7] 写入 news_items...")
        final_counts: dict[str, int] = {}

        for cat, pool in category_pools.items():
            written = 0
            for art in pool:
                if written >= FINAL_PER_CATEGORY:
                    break
                result = summary_results.get(art.id)
                if result is None:
                    logger.debug(f"  跳过（摘要失败）: {art.title[:40]}")
                    continue

                src = db.query(Source).get(art.source_id)
                source_name = src.name if src else "未知来源"

                item = NewsItem(
                    date=today,
                    category=cat,
                    importance=art.importance or 50,
                    title=art.title,
                    summary=result.get("summary"),
                    full_summary=result.get("full_summary"),
                    viewpoints=result.get("viewpoints"),
                    background=result.get("background"),
                    source_links=[{"name": source_name, "url": art.link}],
                    raw_article_id=art.id,
                )
                db.add(item)
                written += 1

            db.commit()
            final_counts[cat] = written
            _pipeline_progress["categories_done"] += 1
            _pipeline_progress["step"] = f"已完成 {_pipeline_progress['categories_done']}/10 板块"
            logger.info(f"  {cat}: 写入 {written} 条")

        total = sum(final_counts.values())
        logger.info(f"===== 流水线完成：{today}，共 {total} 条 =====")
        _pipeline_progress["step"] = f"完成，共 {total} 条新闻"
        return final_counts
    finally:
        _pipeline_progress["running"] = False
