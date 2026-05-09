# Todo — 每日新闻早报网站

> 每个任务包含：目标、产出、验收标准。完成后打勾。

---

## Phase 0：脚手架

### T01 项目初始化 ✅
- [x] 创建 `backend/` 与 `frontend/` 目录
- [x] 编写根 `.gitignore`
- [x] 编写根 `README.md` 占位

### T02 后端 hello world ✅
- [x] 创建 Python 虚拟环境，安装依赖
- [x] `GET /api/health` 返回 `{"ok": true}`
- [x] `config.py` / `db.py` / `models.py` 就绪

### T03 前端 hello world ✅
- [x] Next.js 14 + Tailwind + shadcn/ui 初始化
- [x] `lib/api.ts` 封装，CORS 配好
- [x] 前端能调通后端 health 接口

### 🔍 Checkpoint A ✅
- [x] 前后端能独立启动
- [x] 前端能成功调通后端 API（CORS 通畅）

---

## Phase 1：单源端到端

### T04 RSS 配置 + 单源拉取 ✅
- [x] `sources.yaml`（用 36氪替代已下线的机器之心）、`categories.yaml` 10 个板块
- [x] `pipeline/fetcher.py` + `utils/http.py`

### T05 数据模型 + 写入 ✅
- [x] `models.py`：Source / RawArticle / NewsItem / Favorite
- [x] 启动时同步 sources 表，fetcher 写入 raw_articles 去重

### T06 正文提取 ✅
- [x] `pipeline/extractor.py`：trafilatura，失败降级用 raw_summary
- [x] 30/30 条均有 full_text（12 条真实正文，其余降级）

### T07 LLM 摘要 ✅
- [x] `pipeline/summarizer.py`，LLM JSON 输出
- [x] news_items 写入 3 条，字段完整

### T08 API：新闻列表与详情 ✅
- [x] `GET /api/news` 与 `GET /api/news/{id}`，含 is_favorited

### T09 前端：单板块卡片 + 抽屉 ✅
- [x] NewsCard + NewsDrawer（shadcn Sheet）
- [x] Linear 风格视觉：米白背景、细边框、hover 微动效、重要条目左侧蓝线

### 🔍 Checkpoint B ✅
- [x] 全链路打通：36氪拉取 → 正文提取 → LLM 摘要 → API → 前端卡片 + 抽屉
- [x] 本机端到端可重现

---

## Phase 2：完整流水线

### T10 全部 RSS 源 + 代理 + 容错 ✅
- [x] `sources.yaml` 补全 45 个源（15 国内已验证 200 OK，30 海外开 VPN 后 ok），标注 `use_proxy`
- [x] `.env` 已有 `PROXY_URL=http://127.0.0.1:7890`
- [x] `fetcher` 并发拉取（asyncio + semaphore=10）
- [x] 单源失败：log warning，更新 `last_status=failed`，不影响其他源
- [x] `python -m app.scripts.probe_sources` 探测脚本就绪

### T11 AI 分类 + 重要度 ✅
- [x] `pipeline/classifier.py`：批量分类（每批 40 条标题+摘要）
- [x] Prompt 输出每条 `{category, importance, keep}`，category ∈ 10 个板块 key 或 "other"
- [x] keep=false 或 category=other 的标记为 other（过滤掉）
- [x] 直接更新 raw_articles 的 category/importance 字段

### T12 Orchestrator ✅
- [x] `pipeline/orchestrator.py`：7 步流水线
- [x] 每板块 importance desc 取 top-8 → 提取正文 → 摘要 → 取 top-6 写入 news_items
- [x] 单条摘要失败时跳过，从备选补
- [x] 全过程详细日志

### T13 调度 ✅
- [x] `scheduler.py`：APScheduler AsyncIOScheduler，cron 08:00 Asia/Shanghai，misfire_grace_time=3600
- [x] 注册到 FastAPI lifespan（start/stop）

### T14 兜底 API ✅
- [x] `POST /api/admin/refresh`：后台任务触发流水线，立刻返回 `{status: "started"}`
- [x] `GET /api/admin/status`：返回 `{today_count, pipeline_running, last_run, sources}`
- [x] 防重复：正在运行时返回 already_running
- [x] `GET /api/categories`：返回 10 个板块及今日各板块条数

### 🔍 Checkpoint C ✅
- [x] 完整流水线跑通，10 板块 × 6 条（共 60 条）
- [x] 海外源覆盖：ai(FT)、chip(Bloomberg×3)、robotics(TechCrunch/Verve/Bloomberg/arXiv)、security(Wired/Krebs/Bloomberg/arXiv)、social(Nature×2/arXiv×2)、business(FT/TechCrunch)
- [x] international 板块修复：禁用 xinhua_tech，新增 BBC News/Al Jazeera/Guardian World/NPR World，65/118 篇归入 international
- [x] 兜底机制工作（refresh + status API）

---

## Phase 3：完整 UI

### T15 板块 Tab ✅
- [x] `components/CategoryTabs.tsx`：顶部水平 tab，调用 `/api/categories`
- [x] 切换 tab 重新请求对应板块新闻（useEffect + URL 同步）
- [x] URL 同步（`?category=ai`）
- **验收**：10 个板块切换流畅，每个都看到 6 条卡片

### T16 卡片样式精修 ✅
- [x] 配色：背景 `#FAFAF9`/卡片 `#FFFFFF`/文字 `#0F0F0F`/次要 `#525252`/强调色 `#1E3A5F`
- [x] 卡片：圆角 12px、1px 淡边框、hover `-translate-y-0.5` + 阴影
- [x] 信息层级：标题 15px/600、摘要 13px/`#525252`、元数据 12px/`#A3A3A3`
- [x] 重要度高（≥70）左侧 3px 强调色细线
- **验收**：截图与 Linear/Vercel 风格对比，"简洁高级"无违和感

### T17 抽屉详情完整化 ✅
- [x] 抽屉宽度：桌面 520px，移动端全屏
- [x] 内容区：板块徽章+日期+来源数 / 一句话摘要（高亮块）/ 详细总结 / 观点列表 / 背景 / 原文链接
- [x] 收藏按钮固定在抽屉右上角
- [x] 关闭：ESC、点击遮罩、右上角 X（shadcn Sheet 自带）
- **验收**：抽屉视觉与卡片协调，所有 AI 字段完整展示

### T18 收藏功能 ✅
- [x] `POST /api/favorites` 与 `DELETE /api/favorites/{news_item_id}` 与 `GET /api/favorites`
- [x] `components/FavoriteButton.tsx`：书签图标，点击切换，乐观更新
- [x] 卡片右上角（hover 显示）+ 抽屉右上角都可收藏
- [x] `app/favorites/page.tsx`：收藏列表（按收藏时间倒序，分页）
- [x] 顶部导航加"收藏"链接
- **验收**：PC 收藏一条 → 手机打开收藏页能看到；取消收藏后消失

### T19 日期切换 ✅
- [x] `components/DateSwitcher.tsx`：今天 / 昨天 / 日期选择器
- [x] 选历史日期时调 `/api/news?date=`（URL 同步）
- [x] 历史日期空数据时显示"该日期暂无内容"提示
- **验收**：能切换查看前几天的新闻（前提是那几天有数据）

### T20 响应式 + 状态 ✅
- [x] 移动端：卡片单列（max-w-3xl 自然适配），板块 tab 横向滚动（scrollbar-none）
- [x] 加载态：`NewsSkeleton` 骨架屏（6条 animate-pulse）
- [x] 空状态：今日空数据时显示"立即抓取"按钮，调 refresh + 5s 轮询 status
- [x] 错误态：网络错误提示 + 指引
- **验收**：手机访问 `http://电脑IP:3000` 体验顺畅

### 🔍 Checkpoint D
- [x] 整体 UI 达到"简洁高级"目标
- [x] PC + 手机 + 平板都能正常使用（响应式布局）
- [x] 收藏跨设备同步（后端 SQLite 统一存储）

---

## Phase 4：打磨

### T21 冒烟测试 ✅
- [x] `tests/test_api.py`：覆盖 health / news / favorites / admin（20 个用例）
- [x] `tests/test_classifier.py`：mock LLM，验证解析逻辑（11 个用例）
- [x] `pytest` 全部通过（31 passed）
- **验收**：`cd backend && pytest` 全绿 ✅

### T22 README ✅
- [x] 项目简介
- [x] 系统要求（Python 3.11+, Node 18+, 代理工具）
- [x] 快速启动：4 步（装依赖、配 .env、启动）
- [x] 配置说明：sources.yaml / categories.yaml / .env（含 .env.example）
- [x] 常见问题：VPN、海外源失败、LLM 余额、SQLite 损坏、板块不足 6 条、首页空白
- [x] 后续部署到云服务器的迁移提示
- [x] API 概览表
- **验收**：照着 README 在另一个目录能复现 ✅

### T23 首次访问触发体验 ✅
- [x] 前端首页发现今日无数据时自动调用 `/api/admin/refresh`
- [x] 每 5 秒轮询 `/api/admin/status`，完成后自动刷新
- [x] 显示进度条（step_index / total_steps）+ 步骤文字（如"AI 正在分类与评分..."）
- [x] 后端 orchestrator 追踪 7 步进度 + 板块完成数
- [x] 流水线异常时 finally 重置 running 状态
- **验收**：清空当日数据并刷新页面，体验不突兀 ✅

### 🔍 Checkpoint E
- [x] README 自洽，可复现
- [ ] 单日实测成本 ≤ ¥2（需实际运行一天验证）
- [x] 项目可作为日常工具长期使用

---

## 完成总览

- [x] Phase 0 完成
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 完成
- [x] Phase 4 完成
