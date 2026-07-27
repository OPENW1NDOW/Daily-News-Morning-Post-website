"""
流水线编排：RSS 主线 + Following 旁路。
RSS: fetch → time_filter → classify → select_top → extract → summarize → persist
Following: sync → fetch tweets → filter → select → upsert
支持分类和摘要的并发处理。
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from ..utils.logger import get_logger
from ..utils.timeutil import CST, business_date
from .classifier import CATEGORIES
from .following_branch import run_following_branch

logger = get_logger(__name__)

TOP_PER_CATEGORY = 8   # 每板块取 top-8 进入摘要，保留 6 条
FINAL_PER_CATEGORY = 6
LOOKBACK_HOURS = 24

# 流水线进度（供 admin status API 轮询）
# 1–7: RSS 主线；8: Following 旁路
TOTAL_PIPELINE_STEPS = 8
_pipeline_progress: dict = {
    "running": False,
    "step": "",
    "step_index": 0,
    "total_steps": TOTAL_PIPELINE_STEPS,
    "categories_done": 0,
    "total_categories": len(CATEGORIES),
}
_progress_lock = threading.Lock()


def _update_progress(**kwargs):
    with _progress_lock:
        _pipeline_progress.update(kwargs)


def get_pipeline_progress() -> dict:
    with _progress_lock:
        return dict(_pipeline_progress)


# ── 流水线互斥锁 ─────────────────────────────────────────────
# 用法契约（admin API 与调度器共同遵守）：触发方在启动前 acquire_pipeline_lock()，
# 同步执行体（admin._run_pipeline_sync / scheduler._run_pipeline_sync）finally 里
# release_pipeline_lock()。锁的持有横跨"触发线程 → 执行线程"，因此运行入口
# _run_daily_async 内部不再重复 acquire，否则手动路径会被自己持有的锁挡住。
_pipeline_run_lock = threading.Lock()


def acquire_pipeline_lock() -> bool:
    """非阻塞尝试获取流水线互斥锁；已被持有返回 False。"""
    return _pipeline_run_lock.acquire(blocking=False)


def release_pipeline_lock() -> None:
    """释放流水线互斥锁；未持有时静默忽略（容忍脚本直调 run_daily 的路径）。"""
    try:
        _pipeline_run_lock.release()
    except RuntimeError:
        pass


def run_daily(db, trigger: str = "scheduler") -> dict:
    """
    同步入口，供 admin API 与调度器（均在线程池中调用，无运行中的事件循环）使用。
    返回每板块最终写入条数的汇总 dict。
    """
    return asyncio.run(_run_daily_async(db, trigger=trigger))


async def _run_rss_pipeline(db, target_date, day_start, day_end) -> tuple[dict, int]:
    """RSS 主线 steps 1–7。返回 (每板块写入条数, 分类最终失败批次数)。
    无候选时返回 ({}, 0)（不提前结束外层）。"""
    from ..models import Source, RawArticle
    from .fetcher import fetch_and_save_all_async
    from .classifier import classify_articles
    from .extractor import extract_text
    from .summarizer import summarize
    from .persist import upsert_rss_items

    # ── Step 1: 拉取所有启用源 ─────────────────────────────
    _update_progress(step="正在拉取 RSS 源...", step_index=1)
    logger.info("[1/7] 拉取 RSS 源...")
    sources = db.query(Source).filter_by(enabled=True).all()
    fetch_counts = await fetch_and_save_all_async(db, sources)
    total_fetched = sum(fetch_counts.values())
    logger.info(f"[1/7] 共拉取 {total_fetched} 条新原始文章")

    # ── Step 2: 过滤当日文章 ──────────────────────────
    _update_progress(step="正在筛选当日文章...", step_index=2)
    logger.info(f"[2/7] 过滤 {target_date} 文章...")
    # published_at 以 UTC 墙钟存储（SQLite 丢 tzinfo），查询边界须先转 UTC 再去 tzinfo，
    # 否则 CST 墙钟直接比较会造成 8 小时窗口错位
    day_start_utc = day_start.astimezone(timezone.utc).replace(tzinfo=None)
    day_end_utc = day_end.astimezone(timezone.utc).replace(tzinfo=None)
    candidates = db.query(RawArticle).filter(
        RawArticle.published_at >= day_start_utc,
        RawArticle.published_at < day_end_utc,
    ).all()
    logger.info(f"[2/7] 候选文章：{len(candidates)} 条")

    if not candidates:
        logger.warning("无候选文章，RSS 主线结束（仍继续 Following 旁路）")
        return {}, 0

    # ── Step 3: AI 分类 + 重要度 ───────────────────────────
    _update_progress(step="AI 正在分类与评分...", step_index=3)
    logger.info("[3/7] AI 分类与重要度评分...")
    _, classify_failed_batches = classify_articles(db, candidates)
    if classify_failed_batches:
        logger.warning(f"[3/7] 有 {classify_failed_batches} 个分类批次最终失败")

    # ── Step 4: 每板块按 importance 取 top-8 ─────────────
    _update_progress(step="正在筛选每个板块的候选...", step_index=4)
    logger.info("[4/7] 按板块筛选 top-8...")
    category_pools: dict[str, list] = {cat: [] for cat in CATEGORIES}
    for art in candidates:
        if art.category in CATEGORIES:
            category_pools[art.category].append(art)

    for cat in CATEGORIES:
        category_pools[cat].sort(key=lambda a: (a.importance or 0), reverse=True)
        category_pools[cat] = category_pools[cat][:TOP_PER_CATEGORY]
        logger.info(f"  {cat}: {len(category_pools[cat])} 条候选")

    # ── Step 5: 提取正文（并发） ────────────────────────────
    _update_progress(step="正在提取新闻正文...", step_index=5)
    logger.info("[5/7] 正文提取（并发 3）...")
    all_selected = [art for pool in category_pools.values() for art in pool]

    # 主线程预取 (id, link, use_proxy)，避免子线程触发 SQLAlchemy lazy loading
    _extract_targets = []
    for art in all_selected:
        if art.full_text:
            continue
        src = db.get(Source, art.source_id)
        _extract_targets.append((art.id, art.link, src.use_proxy if src else False))

    extracted: dict[int, str | None] = {}
    if _extract_targets:
        def _extract_one(item):
            art_id, link, use_proxy = item
            return art_id, extract_text(link, use_proxy=use_proxy)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_extract_one, item) for item in _extract_targets]
            done = 0
            for future in as_completed(futures):
                art_id, text = future.result()
                extracted[art_id] = text
                done += 1
                if done % 5 == 0 or done == len(_extract_targets):
                    logger.info(f"  正文提取进度：{done}/{len(_extract_targets)}")
                    _update_progress(step=f"正在提取新闻正文... {done}/{len(_extract_targets)}")

    for art in all_selected:
        if art.full_text:
            continue
        art.full_text = extracted.get(art.id) or art.raw_summary or art.title
    db.commit()
    logger.info(f"[5/7] 正文提取完成（共 {len(all_selected)} 篇，新提取 {len(_extract_targets)} 篇）")

    # ── Step 6: 生成摘要（并发） ────────────────────────────
    _update_progress(step="AI 正在生成摘要...", step_index=6)
    logger.info("[6/7] 生成 AI 摘要（并发 3）...")
    summary_results: dict[int, dict | None] = {}

    # 主线程预提取文本，避免子线程触发 SQLAlchemy lazy loading
    _articles_data = [
        (art.id, art.title, art.full_text or art.raw_summary or art.title)
        for art in all_selected
    ]

    def _summarize_one(item):
        art_id, title, text = item
        result = summarize(title, text)
        return art_id, result

    # 并发生成摘要
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_summarize_one, item): item for item in _articles_data}
        completed = 0
        for future in as_completed(futures):
            art_id, result = future.result()
            summary_results[art_id] = result
            completed += 1
            if completed % 10 == 0 or completed == len(all_selected):
                logger.info(f"  摘要进度：{completed}/{len(all_selected)}")

    # ── Step 7: 写入 news_items ──────────────────────────────
    _update_progress(step="正在写入结果...", step_index=7)
    logger.info("[7/7] 写入 news_items...")
    final_counts: dict[str, int] = {}

    for cat, pool in category_pools.items():
        rows = []
        for art in pool:
            if len(rows) >= FINAL_PER_CATEGORY:
                break
            result = summary_results.get(art.id)
            if result is None:
                logger.debug(f"  跳过（摘要失败）: {art.title[:40]}")
                continue
            src = db.get(Source, art.source_id)
            source_name = src.name if src else "未知来源"
            rows.append({
                "raw_article_id": art.id,
                "importance": art.importance or 50,
                "title": art.title,
                "summary": result.get("summary"),
                "full_summary": result.get("full_summary"),
                "viewpoints": result.get("viewpoints"),
                "background": result.get("background"),
                "source_links": [{"name": source_name, "url": art.link}],
            })
        written = upsert_rss_items(db, target_date=target_date, category=cat, rows=rows)
        db.commit()
        final_counts[cat] = written
        with _progress_lock:
            _pipeline_progress["categories_done"] += 1
            done = _pipeline_progress["categories_done"]
        _update_progress(step=f"已完成 {done}/{len(CATEGORIES)} 板块")
        logger.info(f"  {cat}: 写入 {written} 条")

    total = sum(final_counts.values())
    logger.info(f"===== RSS 主线完成：{target_date}，共 {total} 条 =====")
    _update_progress(step=f"RSS 写入完成（{total} 条），准备 Following…")
    return final_counts, classify_failed_batches


async def _run_daily_async(db, trigger: str = "scheduler") -> dict:
    from ..models import PipelineRun

    run_record = PipelineRun(trigger=trigger, status="running")
    db.add(run_record)
    db.commit()
    db.refresh(run_record)

    now_cst = datetime.now(CST)
    target_date = business_date(now_cst)
    day_start = now_cst - timedelta(hours=LOOKBACK_HOURS)
    day_end = now_cst
    logger.info(f"===== 流水线开始：{target_date} =====")
    logger.info(f"抓取窗口：{day_start.strftime('%m-%d %H:%M')} ~ {day_end.strftime('%m-%d %H:%M')} CST")
    _update_progress(
        running=True,
        categories_done=0,
        step_index=0,
        total_steps=TOTAL_PIPELINE_STEPS,
        step="流水线启动中…",
    )

    run_id = run_record.id
    try:
        final_counts = {}
        classify_failed_batches = 0
        rss_error = None
        try:
            final_counts, classify_failed_batches = await _run_rss_pipeline(
                db, target_date, day_start, day_end
            )
        except Exception as e:
            rss_error = str(e)[:500]
            logger.exception("RSS pipeline failed")
            db.rollback()
            run_record = db.get(PipelineRun, run_id)
            if run_record is None:
                raise RuntimeError(f"PipelineRun(id={run_id}) 在回滚后丢失，无法记录运行结果")

        _update_progress(
            step="正在抓取 X Following…",
            step_index=TOTAL_PIPELINE_STEPS,
        )
        following_result = {"status": "skipped", "written": 0, "error": None}
        try:
            following_result = await run_following_branch(
                db,
                target_date,
                day_start,
                day_end,
                on_progress=lambda msg: _update_progress(
                    step=msg,
                    step_index=TOTAL_PIPELINE_STEPS,
                ),
            )
        except Exception as e:
            following_result = {"status": "error", "written": 0, "error": str(e)[:500]}
            logger.exception("Following branch failed")
            db.rollback()
            run_record = db.get(PipelineRun, run_id)
            if run_record is None:
                raise RuntimeError(f"PipelineRun(id={run_id}) 在回滚后丢失，无法记录运行结果")

        rss_total = sum(final_counts.values()) if final_counts else 0
        fol_status = following_result.get("status")
        fol_written = int(following_result.get("written") or 0)
        if fol_status == "skipped":
            done_msg = f"完成：RSS {rss_total} 条（Following 已跳过）"
        elif fol_status == "error":
            done_msg = f"完成：RSS {rss_total} 条；Following 失败"
        else:
            done_msg = f"完成：RSS {rss_total} 条 + Following {fol_written} 条"
        _update_progress(step=done_msg, step_index=TOTAL_PIPELINE_STEPS)

        result_payload = {**final_counts, "following": following_result}
        if classify_failed_batches:
            result_payload["classify_failed_batches"] = classify_failed_batches
        run_record.result = result_payload
        if rss_error:
            run_record.status = "error"
            run_record.error = rss_error
        else:
            run_record.status = "success"
        run_record.finished_at = datetime.now(timezone.utc)
        db.commit()
        return run_record.result
    finally:
        _update_progress(running=False)
