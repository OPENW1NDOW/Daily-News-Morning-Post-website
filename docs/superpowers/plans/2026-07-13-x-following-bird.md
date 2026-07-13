# X Following + Favorites Upsert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用稳定键 upsert 修复同日重跑冲掉收藏，并增加基于 bird 的 X Following 旁路板块（与主线互不影响）。

**Architecture:** 抽出 `persist.py` 负责 RSS/`following` 的 upsert；`orchestrator` 去掉 Step0 全日删除，主线与 Following 旁路各自 try/except、串行执行。Following 推文不入 `raw_articles`；账号进 `x_accounts`；bird 经 `bird_client` 封装，Docker 镜像安装 Node + 钉死 bird。

**Tech Stack:** FastAPI、SQLAlchemy/SQLite、`create_all`、pytest、Next.js 16、bird CLI（Cookie）、DeepSeek 兼容 OpenAI SDK

**Spec:** `docs/superpowers/specs/2026-07-13-x-following-bird-design.md`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/pipeline/persist.py` | **新建** — RSS / following 的 upsert + 条件删除 |
| `backend/app/pipeline/orchestrator.py` | 去掉 Step0 硬删；调用 persist；串行旁路 |
| `backend/app/models.py` | 新增 `XAccount` |
| `backend/app/config.py` | `x_auth_token` / `x_ct0` / `bird_bin` / candidate top N |
| `backend/app/pipeline/bird_client.py` | **新建** — bird CLI 封装 |
| `backend/app/pipeline/sync_x_following.py` | **新建** — Following 名单同步 |
| `backend/app/pipeline/tweet_filter.py` | **新建** — 规则过滤 |
| `backend/app/pipeline/following_select.py` | **新建** — LLM 精选 |
| `backend/app/pipeline/following_branch.py` | **新建** — 旁路编排 |
| `backend/app/api/admin.py` | X Following admin 端点 |
| `backend/config/categories.yaml` | 追加 `following`（**不改** `classifier.CATEGORIES`） |
| `backend/Dockerfile` | 安装 Node + bird |
| `backend/.env.example` | Cookie / bird 变量 |
| `frontend/app/HomeContent.tsx` | Hero 排除 `following` |
| `frontend/components/admin/XFollowingManager.tsx` | **新建** — 后台 Tab |
| `frontend/app/admin/page.tsx` | 挂载 Tab |
| `frontend/lib/api.ts` / `types.ts` | API 与类型 |
| `backend/tests/test_persist.py` | **新建** |
| `backend/tests/test_x_following.py` | **新建** |
| `backend/tests/test_tweet_filter.py` | **新建** |
| `SESSION_LOG.md` | 记录 |

---

### Task 1: Persist upsert（收藏安全落库）

**Files:**
- Create: `backend/app/pipeline/persist.py`
- Create: `backend/tests/test_persist.py`
- Modify: `backend/app/models.py`（仅确认 `NewsItem` / `Favorite` 字段，本任务可不改模型）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_persist.py
from datetime import date
from app.models import NewsItem, Favorite, User
from app.pipeline.persist import upsert_rss_items, EXTERNAL_ID_KEY


def test_rss_upsert_keeps_id_and_favorite(db):
    d = date.today()
    item = NewsItem(
        date=d, category="ai", importance=80, title="旧标题",
        summary="旧", raw_article_id=101,
        source_links=[{"name": "源", "url": "https://example.com/a"}],
    )
    db.add(item)
    db.flush()
    user = User(username="u1", password_hash="x")
    db.add(user)
    db.flush()
    db.add(Favorite(user_id=user.id, news_item_id=item.id))
    db.commit()
    old_id = item.id

    written = upsert_rss_items(
        db,
        target_date=d,
        category="ai",
        rows=[
            {
                "raw_article_id": 101,
                "importance": 90,
                "title": "新标题",
                "summary": "新摘要",
                "full_summary": "全文",
                "viewpoints": ["a"],
                "background": "bg",
                "source_links": [{"name": "源", "url": "https://example.com/a"}],
            }
        ],
    )
    db.commit()
    assert written == 1
    again = db.query(NewsItem).filter_by(id=old_id).one()
    assert again.title == "新标题"
    assert again.importance == 90
    assert db.query(Favorite).filter_by(news_item_id=old_id).count() == 1


def test_rss_deletes_unfavorited_absent_from_new_set(db):
    d = date.today()
    keep = NewsItem(date=d, category="ai", importance=80, title="留", raw_article_id=1, source_links=[])
    drop = NewsItem(date=d, category="ai", importance=50, title="丢", raw_article_id=2, source_links=[])
    db.add_all([keep, drop])
    db.commit()

    upsert_rss_items(
        db,
        target_date=d,
        category="ai",
        rows=[{
            "raw_article_id": 1,
            "importance": 80,
            "title": "留",
            "summary": None,
            "full_summary": None,
            "viewpoints": None,
            "background": None,
            "source_links": [],
        }],
    )
    db.commit()
    ids = {n.raw_article_id for n in db.query(NewsItem).filter_by(date=d, category="ai").all()}
    assert ids == {1}


def test_rss_keeps_favorited_even_if_absent_from_new_set(db):
    d = date.today()
    fav_item = NewsItem(date=d, category="ai", importance=50, title="藏", raw_article_id=2, source_links=[])
    db.add(fav_item)
    db.flush()
    user = User(username="u2", password_hash="x")
    db.add(user)
    db.flush()
    db.add(Favorite(user_id=user.id, news_item_id=fav_item.id))
    db.commit()

    upsert_rss_items(db, target_date=d, category="ai", rows=[])
    db.commit()
    assert db.query(NewsItem).filter_by(id=fav_item.id).one().title == "藏"


def test_following_upsert_by_external_id(db):
    from app.pipeline.persist import upsert_following_items
    d = date.today()
    item = NewsItem(
        date=d, category="following", importance=70, title="旧推",
        raw_article_id=None,
        source_links=[{"name": "@a", "url": "https://x.com/i/status/99", "external_id": "99"}],
    )
    db.add(item)
    db.commit()
    old_id = item.id

    upsert_following_items(
        db,
        target_date=d,
        rows=[{
            "external_id": "99",
            "importance": 88,
            "title": "新推",
            "summary": "s",
            "full_summary": "s",
            "viewpoints": None,
            "background": None,
            "handle": "a",
            "url": "https://x.com/i/status/99",
        }],
    )
    db.commit()
    assert db.get(NewsItem, old_id).title == "新推"
    assert db.get(NewsItem, old_id).importance == 88
```

- [ ] **Step 2: 跑测试确认失败**

Run（在 `backend/`）:

```bash
pytest tests/test_persist.py -v
```

Expected: FAIL（`persist` 模块不存在）

- [ ] **Step 3: 实现 `persist.py`**

```python
# backend/app/pipeline/persist.py
"""按稳定键 upsert news_items，避免同日重跑冲掉 favorites。"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..models import Favorite, NewsItem

EXTERNAL_ID_KEY = "external_id"
FOLLOWING_CATEGORY = "following"


def _favorited_ids(db: Session, news_item_ids: list[int]) -> set[int]:
    if not news_item_ids:
        return set()
    rows = (
        db.query(Favorite.news_item_id)
        .filter(Favorite.news_item_id.in_(news_item_ids))
        .all()
    )
    return {r[0] for r in rows}


def _apply_fields(item: NewsItem, row: dict) -> None:
    item.importance = row["importance"]
    item.title = row["title"]
    item.summary = row.get("summary")
    item.full_summary = row.get("full_summary")
    item.viewpoints = row.get("viewpoints")
    item.background = row.get("background")
    item.source_links = row.get("source_links")


def upsert_rss_items(
    db: Session,
    *,
    target_date: date,
    category: str,
    rows: list[dict],
) -> int:
    """稳定键 (date, raw_article_id)。返回写入/更新条数。"""
    existing = (
        db.query(NewsItem)
        .filter(NewsItem.date == target_date, NewsItem.category == category)
        .all()
    )
    by_raw = {n.raw_article_id: n for n in existing if n.raw_article_id is not None}
    keep_raw_ids: set[int] = set()
    written = 0

    for row in rows:
        rid = row["raw_article_id"]
        keep_raw_ids.add(rid)
        item = by_raw.get(rid)
        if item is None:
            item = NewsItem(
                date=target_date,
                category=category,
                raw_article_id=rid,
                importance=row["importance"],
                title=row["title"],
            )
            db.add(item)
            by_raw[rid] = item
        _apply_fields(item, row)
        written += 1

    fav_ids = _favorited_ids(db, [n.id for n in existing if n.id is not None])
    for n in list(existing):
        if n.raw_article_id in keep_raw_ids:
            continue
        if n.id in fav_ids:
            continue
        db.delete(n)

    db.flush()
    return written


def _external_id_from_item(item: NewsItem) -> str | None:
    links = item.source_links or []
    if not links:
        return None
    ext = links[0].get(EXTERNAL_ID_KEY) if isinstance(links[0], dict) else None
    return str(ext) if ext is not None else None


def upsert_following_items(
    db: Session,
    *,
    target_date: date,
    rows: list[dict],
) -> int:
    """稳定键 (date, category=following, external_id in source_links)。"""
    existing = (
        db.query(NewsItem)
        .filter(NewsItem.date == target_date, NewsItem.category == FOLLOWING_CATEGORY)
        .all()
    )
    by_ext = {}
    for n in existing:
        ext = _external_id_from_item(n)
        if ext:
            by_ext[ext] = n

    keep: set[str] = set()
    written = 0
    for row in rows:
        ext = str(row["external_id"])
        keep.add(ext)
        links = [{
            "name": f"@{row['handle'].lstrip('@')}",
            "url": row["url"],
            EXTERNAL_ID_KEY: ext,
        }]
        payload = {
            "importance": row["importance"],
            "title": row["title"],
            "summary": row.get("summary"),
            "full_summary": row.get("full_summary"),
            "viewpoints": row.get("viewpoints"),
            "background": row.get("background"),
            "source_links": links,
        }
        item = by_ext.get(ext)
        if item is None:
            item = NewsItem(
                date=target_date,
                category=FOLLOWING_CATEGORY,
                raw_article_id=None,
                importance=payload["importance"],
                title=payload["title"],
                source_links=links,
            )
            db.add(item)
            by_ext[ext] = item
        _apply_fields(item, payload)
        written += 1

    fav_ids = _favorited_ids(db, [n.id for n in existing if n.id is not None])
    for n in list(existing):
        ext = _external_id_from_item(n)
        if ext in keep:
            continue
        if n.id in fav_ids:
            continue
        db.delete(n)

    db.flush()
    return written
```

- [ ] **Step 4: 跑测试确认通过**

```bash
pytest tests/test_persist.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/persist.py backend/tests/test_persist.py
git commit -m "feat: upsert news_items by stable key to preserve favorites"
```

---

### Task 2: Orchestrator 改用 upsert（去掉 Step0 硬删）

**Files:**
- Modify: `backend/app/pipeline/orchestrator.py`
- Test: `backend/tests/test_persist.py`（可加集成向 mock，或依赖现有 pipeline 测试若有）

- [ ] **Step 1: 写失败测试（二次 persist 保留 id）**

在 `test_persist.py` 已覆盖单元行为。本任务加 orchestrator 级冒烟（mock 摘要路径过重时可跳过，改为手动检查 diff）：至少用测试锁定「Step0 全日 delete 已不存在」。

```python
# backend/tests/test_orchestrator_persist.py
import inspect
from app.pipeline import orchestrator


def test_orchestrator_no_longer_deletes_all_news_for_day():
    src = inspect.getsource(orchestrator._run_daily_async)
    assert "NewsItem.date == target_date).delete()" not in src.replace(" ", "")
    # 更稳：断言调用 upsert
    assert "upsert_rss_items" in src
```

（若源码格式导致断言脆，改为：`assert "upsert_rss_items" in inspect.getsource(orchestrator)`）

- [ ] **Step 2: 跑测试确认失败**

```bash
pytest tests/test_orchestrator_persist.py -v
```

Expected: FAIL

- [ ] **Step 3: 改 orchestrator Step7**

删除 Step0 整块（约 L73–78 的全日 `delete`）。

将 Step7 写入改为：

```python
from .persist import upsert_rss_items

# 在 category 循环内，收集 rows 后：
rows = []
for art in pool:
    if len(rows) >= FINAL_PER_CATEGORY:
        break
    result = summary_results.get(art.id)
    if result is None:
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
```

保留进度与 `run_record` 逻辑。

- [ ] **Step 4: 跑相关测试**

```bash
pytest tests/test_orchestrator_persist.py tests/test_persist.py tests/test_api.py -v
```

Expected: PASS（若 `test_api` 依赖旧 delete 语义，按失败信息微调测试数据）

- [ ] **Step 5: Commit**

```bash
git add backend/app/pipeline/orchestrator.py backend/tests/test_orchestrator_persist.py
git commit -m "refactor: pipeline persist via upsert instead of daily wipe"
```

---

### Task 3: Hero 排除 following + categories.yaml

**Files:**
- Modify: `frontend/app/HomeContent.tsx`（约 L85–94）
- Modify: `backend/config/categories.yaml`
- Modify: `frontend/components/NewsDrawer.tsx`（确认 `viewpoints`/`background` 空值不崩；若会崩则加可选链）

- [ ] **Step 1: 改 Hero 选取**

```tsx
const hero = all
  .filter((it) => it.category !== "following")
  .reduce((a, b) => (b.importance > a.importance ? b : a), null as NewsItem | null)
// 注意：空数组时 reduce 初值；若 filter 后为空则 hero=null
```

推荐写法：

```tsx
const candidates = all.filter((it) => it.category !== "following")
const hero = candidates.length
  ? candidates.reduce((a, b) => (b.importance > a.importance ? b : a))
  : null
```

sectionItems 仍按原逻辑从各分类去掉 hero.id。

- [ ] **Step 2: categories.yaml 追加**（保持顶层 `categories:`）

```yaml
  - key: following
    name: Following
    description: 你在 X 上关注的博主精选帖（AI / Agent / LLM 向）
```

**禁止**修改 `backend/app/pipeline/classifier.py` 的 `CATEGORIES`。

- [ ] **Step 3: 目视 / 本地确认 Drawer 对 null viewpoints 安全**

若 `viewpoints.map` 无可选，改为 `(item.viewpoints ?? []).map(...)`。

- [ ] **Step 4: Commit**

```bash
git add frontend/app/HomeContent.tsx frontend/components/NewsDrawer.tsx backend/config/categories.yaml
git commit -m "feat: add Following category display; exclude it from Hero"
```

---

### Task 4: `XAccount` 模型 + settings

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/tests/conftest.py`（导入 `XAccount` 以便 `create_all`）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_x_accounts_model.py
from app.models import XAccount


def test_x_account_unique_user_id(db):
    db.add(XAccount(x_user_id="1", handle="a", display_name="A", enabled=True, is_following=True))
    db.commit()
    db.add(XAccount(x_user_id="1", handle="b", display_name="B", enabled=True, is_following=True))
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: 跑测确认失败 → 实现模型**

```python
class XAccount(Base):
    __tablename__ = "x_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    x_user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    handle: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_following: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

Settings 追加：

```python
x_auth_token: str = ""
x_ct0: str = ""
bird_bin: str = "bird"
x_following_candidate_top_n: int = 8
```

`.env.example` 同步注释。

- [ ] **Step 3: 测试通过并 Commit**

```bash
pytest tests/test_x_accounts_model.py -v
git add backend/app/models.py backend/app/config.py backend/.env.example backend/tests/test_x_accounts_model.py
git commit -m "feat: add XAccount model and bird-related settings"
```

---

### Task 5: `bird_client`（可 mock）

**Files:**
- Create: `backend/app/pipeline/bird_client.py`
- Create: `backend/tests/test_bird_client.py`

- [ ] **Step 1: 定义接口与失败测试**

```python
# 期望 API
# list_following() -> list[dict]  # {x_user_id, handle, display_name, avatar_url?}
# fetch_user_tweets(handle: str, since_iso: str, until_iso: str) -> list[dict]
#   # {tweet_id, handle, text, created_at, is_retweet, is_quote}
```

用 `monkeypatch` 替换 `subprocess.run`，断言传入 `settings.bird_bin` 与 env 中的 token。

实现策略（锁定一种，避免开放）：**subprocess 调 CLI**，环境变量 `AUTH_TOKEN`/`CT0`（bird 惯例）从 `settings.x_auth_token`/`x_ct0` 注入。

具体 CLI 子命令以实现时 `bird --help` 为准；封装内集中一处。若 CLI 无 following 列表命令，则用 bird 文档中的等价 GraphQL/子命令；**计划默认**：

```text
bird following --json
bird user-tweets <handle> --json
```

若实际 bird 0.8 API 不同：只改 `bird_client.py` 内命令拼装，不改调用方。

Cookie 缺失时：`BirdAuthError`，由上层跳过旁路。

- [ ] **Step 2: 实现 + 单测 mock subprocess 通过**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: add bird_client wrapper for X following/tweets"
```

---

### Task 6: `sync_x_following`（事务语义）

**Files:**
- Create: `backend/app/pipeline/sync_x_following.py`
- Create: `backend/tests/test_sync_x_following.py`

- [ ] **Step 1: 失败测试**

```python
def test_sync_preserves_enabled_and_marks_unfollowed(db, monkeypatch):
    from app.models import XAccount
    from app.pipeline import sync_x_following as mod

    db.add(XAccount(x_user_id="1", handle="keep", display_name="K", enabled=False, is_following=True))
    db.add(XAccount(x_user_id="2", handle="gone", display_name="G", enabled=True, is_following=True))
    db.commit()

    monkeypatch.setattr(mod, "list_following", lambda: [
        {"x_user_id": "1", "handle": "keep", "display_name": "Keep2", "avatar_url": None},
        {"x_user_id": "3", "handle": "new", "display_name": "New", "avatar_url": None},
    ])
    mod.sync_following_accounts(db)
    db.commit()

    a1 = db.query(XAccount).filter_by(x_user_id="1").one()
    assert a1.enabled is False  # 不覆盖
    assert a1.is_following is True
    assert a1.display_name == "Keep2"
    a2 = db.query(XAccount).filter_by(x_user_id="2").one()
    assert a2.is_following is False
    a3 = db.query(XAccount).filter_by(x_user_id="3").one()
    assert a3.enabled is True


def test_sync_failure_does_not_flip_flags(db, monkeypatch):
    from app.models import XAccount
    from app.pipeline import sync_x_following as mod

    db.add(XAccount(x_user_id="1", handle="a", display_name="A", enabled=True, is_following=True))
    db.commit()

    def boom():
        raise RuntimeError("bird down")

    monkeypatch.setattr(mod, "list_following", boom)
    import pytest
    with pytest.raises(RuntimeError):
        mod.sync_following_accounts(db)
    assert db.query(XAccount).filter_by(x_user_id="1").one().is_following is True
```

- [ ] **Step 2: 实现** — 先 `accounts = list_following()`，成功后再 upsert / 标记；失败直接 raise，不写库。

- [ ] **Step 3: 测试通过 + Commit**

```bash
git commit -m "feat: sync X following list into x_accounts"
```

---

### Task 7: 规则过滤 + LLM 精选

**Files:**
- Create: `backend/app/pipeline/tweet_filter.py`
- Create: `backend/app/pipeline/following_select.py`
- Create: `backend/tests/test_tweet_filter.py`

- [ ] **Step 1: `tweet_filter` 测试与实现**

```python
def filter_tweets(tweets: list[dict], *, min_chars: int = 40) -> list[dict]:
    # 丢弃 is_retweet and not is_quote
    # 丢弃 len(text.strip()) < min_chars
    # 保留原创与 quote
```

- [ ] **Step 2: `following_select.select_tweets(tweets) -> list[dict]`**

批量 LLM，输出带 `keep`/`summary`/`score`；过滤 `keep`；按 score 排序；截断至 `settings.x_following_candidate_top_n`，调用方再 `[:6]` 落库。

Prompt 偏好 AI/Agent/LLM；`temperature=0.1`；复用 `_extract_json` 模式（可从 classifier 小范围导入或复制私有辅助，避免大重构）。

单测：mock OpenAI client。

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: tweet rule filter and LLM selection for Following"
```

---

### Task 8: Following 旁路 + orchestrator 接线

**Files:**
- Create: `backend/app/pipeline/following_branch.py`
- Modify: `backend/app/pipeline/orchestrator.py`
- Create: `backend/tests/test_following_branch.py`

- [ ] **Step 1: 测试**

```python
def test_following_runs_even_if_mainline_fails(db, monkeypatch):
    # monkeypatch _run_mainline_rss 抛错；following_branch 被调用且返回 ok
    ...


def test_bird_failure_does_not_fail_mainline(db, monkeypatch):
    # mainline ok；following raises BirdAuthError；run_daily status success；result["following"]["status"]=="error"
    ...
```

重构建议：把现有 RSS 七步抽成 `_run_rss_pipeline(db, target_date, day_start, day_end) -> dict`，外层：

```python
final_counts = {}
rss_error = None
try:
    final_counts = await _run_rss_pipeline(...)
except Exception as e:
    rss_error = str(e)[:500]

following_result = {"status": "skipped", "written": 0, "error": None}
try:
    following_result = await run_following_branch(db, target_date, day_start, day_end)
except Exception as e:
    following_result = {"status": "error", "written": 0, "error": str(e)[:500]}

run_record.result = {**final_counts, "following": following_result}
run_record.status = "error" if (rss_error and following_result["status"] == "error") else (
    "error" if rss_error else "success"
)
# 建议默认：仅 rss_error 时仍 success=False → status error；仅 following 失败则 status success
# 锁定：rss 失败 → status=error；rss 成功 following 失败 → status=success
if rss_error:
    run_record.status = "error"
    run_record.error = rss_error
else:
    run_record.status = "success"
```

`run_following_branch`：

1. Cookie 空 → `{status:"skipped", ...}`  
2. 若无 enabled 账号且表空 → 尝试 sync 一次  
3. 查 `enabled & is_following`  
4. 串行/并发≤2 拉推文，过滤日界  
5. `filter_tweets` → `select_tweets` → 取前 6  
6. `upsert_following_items`  
7. 返回 `{status:"ok", written:n, error:None}`

日界：使用与 orchestrator 相同的 `day_start`/`day_end`/`target_date`（CST 08:00）。

- [ ] **Step 2: 实现并测通**

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: Following sidecar branch in daily pipeline"
```

---

### Task 9: Admin API

**Files:**
- Modify: `backend/app/api/admin.py`
- Modify: `backend/tests/test_x_following.py`（API 级，需 admin 用户 fixture——参照现有 admin 测试如何造 admin）

- [ ] **Step 1: 端点**

| 方法 | 路径 |
|------|------|
| GET | `/api/admin/x-following/accounts` |
| PATCH | `/api/admin/x-following/accounts/{id}` body `{"enabled": bool}` |
| POST | `/api/admin/x-following/sync` |
| GET | `/api/admin/x-following/status` |

status 返回：

```json
{
  "cookie_configured": true,
  "last_synced_at": "...",
  "following": { "status": "ok", "written": 6, "error": null }
}
```

`following` 取最近一次 `PipelineRun.result["following"]`（若无则 null）。

全部 `Depends(require_admin)`。

- [ ] **Step 2: 测试 + Commit**

```bash
git commit -m "feat: admin API for X Following accounts and sync"
```

---

### Task 10: Admin 前端 Tab

**Files:**
- Create: `frontend/components/admin/XFollowingManager.tsx`
- Modify: `frontend/app/admin/page.tsx`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: API 客户端方法** — `getXFollowingAccounts` / `patchXFollowingAccount` / `syncXFollowing` / `getXFollowingStatus`

- [ ] **Step 2: UI** — 状态条（Cookie / 上次同步 / 上次旁路错误）+ 同步按钮 + 表格开关（对齐现有 SourceManager 风格）

- [ ] **Step 3: `AdminTab` 增加 `"x-following"`**，图标可用 `Twitter` 或 `AtSign`（lucide）

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: admin UI for X Following management"
```

---

### Task 11: Docker 安装 Node + bird

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `backend/.env.example`（再确认）

- [ ] **Step 1: Dockerfile 增加**（在 `pip install` 之后或之前）

```dockerfile
# Node + bird（X Following）
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @steipete/bird@0.8.0 \
    && rm -rf /var/lib/apt/lists/*
```

若 `@steipete/bird@0.8.0` 不可用，改用镜像包名并在 SESSION_LOG 记录实际版本；`BIRD_BIN=bird`。

- [ ] **Step 2: 本地 `docker build` 冒烟（可选，CI 无则手工）**

- [ ] **Step 3: Commit**

```bash
git commit -m "build: install Node and bird in backend image"
```

---

### Task 12: 前端 Following 展示收尾 + SESSION_LOG

**Files:**
- Modify: `frontend/components/NewsCard.tsx` / `SectionBlock`（若需要把 `source_links[0].name` 显示为 @handle——检查现有是否已显示 source）
- Modify: `SESSION_LOG.md`

- [ ] **Step 1: 确认首页拉取 categories 后自动出现 Following 分区**（`HomeContent` 已按 categories 映射）；无额外 Tab 硬编码也可。

- [ ] **Step 2: 卡片来源展示** — 若 NewsCard 已显示来源名，following 的 `@handle` 会自动出现。

- [ ] **Step 3: 全量后端测试**

```bash
cd backend && pytest tests/ -v
```

Expected: 全绿

- [ ] **Step 4: 更新 SESSION_LOG**（做了什么、决策、遗留：Cookie 续期、真机 bird 验证）

- [ ] **Step 5: Commit**

```bash
git commit -m "docs: SESSION_LOG for Following + favorites upsert"
```

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| upsert 收藏修复 | 1–2 |
| Hero 排除 following | 3 |
| categories.yaml / classifier 不加 following | 3 |
| x_accounts + UNIQUE | 4 |
| bird_client / Cookie env | 4–5, 11 |
| sync 事务 / 不覆盖 enabled | 6 |
| 规则 + LLM + Top8→6 | 7–8 |
| 旁路与主线互不影响 | 8 |
| 对齐日界 | 8 |
| Admin API/UI | 9–10 |
| Docker Node/bird | 11 |
| 推文不入 raw_articles | 8（直接 upsert_following） |
| pipeline_runs.result.following | 8–9 |
| 测试 | 各 Task |

## Placeholder / 一致性自检

- bird CLI 子命令名以实现时 `--help` 为准，但调用方只依赖 `list_following` / `fetch_user_tweets`
- `FINAL_PER_CATEGORY = 6` 与 following 落库 6 对齐
- 不把 `following` 写入 `classifier.CATEGORIES`

---

## 执行方式

Plan 完成后可选：

1. **Subagent-Driven（推荐）** — 每 Task 新子代理 + 两阶段审查  
2. **Inline Execution** — 本会话按 executing-plans 连续做  

请选择一种后再开工。
