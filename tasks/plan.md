# 每日新闻早报网站 — 实施计划

> 个人本机版 · 2026/05/08

## 一、项目目标

搭建一个本机运行的每日新闻早报网站，每天 8:00 自动从约 40 个 RSS 源拉取过去 24h 新闻，由 AI 大模型完成筛选、分类、摘要、总结、观点提取和背景补充，按 10 个板块每板块 6 条呈现。前端为简洁高级的卡片信息流，支持跨设备访问与收藏。

---

## 二、技术栈

| 层 | 选型 | 关键库 |
|---|---|---|
| 后端 | Python 3.11+ / FastAPI | feedparser, trafilatura, httpx, APScheduler, openai (兼容各模型服务商) |
| 数据库 | SQLite | SQLAlchemy 2.x + Alembic |
| 调度 | APScheduler | CronTrigger 8:00 + 启动时兜底检查 |
| 前端 | Next.js 14 (App Router) + TypeScript | TailwindCSS, shadcn/ui, SWR, Framer Motion |
| 部署 | 本机 localhost | 后端 8000 端口，前端 3000 端口 |

---

## 三、目录结构

```
新建文件夹/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口
│   │   ├── config.py            # 配置加载
│   │   ├── db.py                # SQLAlchemy 引擎与 session
│   │   ├── models.py            # ORM 模型
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── api/
│   │   │   ├── news.py          # /api/news, /api/news/{id}
│   │   │   ├── favorites.py     # /api/favorites
│   │   │   └── admin.py         # /api/admin/refresh, /api/admin/sources
│   │   ├── pipeline/
│   │   │   ├── fetcher.py       # RSS 拉取（带代理）
│   │   │   ├── extractor.py     # trafilatura 正文提取
│   │   │   ├── classifier.py    # LLM 分类+重要度
│   │   │   ├── summarizer.py    # LLM 摘要+观点+背景
│   │   │   └── orchestrator.py  # 流水线编排：拉取→去重→提取→分类→摘要→存储
│   │   ├── scheduler.py         # APScheduler 8:00 任务 + 兜底检查
│   │   └── utils/
│   │       ├── http.py          # httpx 客户端工厂（按源选代理）
│   │       └── logger.py
│   ├── config/
│   │   ├── sources.yaml         # RSS 源清单（板块、URL、是否走代理）
│   │   └── categories.yaml      # 板块定义（key、显示名、描述）
│   ├── data/
│   │   └── news.db              # SQLite 数据文件（gitignore）
│   ├── logs/
│   │   └── pipeline.log         # gitignore
│   ├── tests/
│   │   ├── test_fetcher.py
│   │   ├── test_classifier.py
│   │   └── test_api.py
│   ├── .env.example             # LLM_API_KEY, PROXY_URL 等
│   ├── .env                     # gitignore
│   ├── requirements.txt
│   └── README.md
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # 主页（卡片流）
│   │   ├── favorites/page.tsx   # 收藏页
│   │   └── api/                 # （可选）Next.js API 代理
│   ├── components/
│   │   ├── CategoryTabs.tsx     # 板块切换
│   │   ├── NewsCard.tsx         # 卡片
│   │   ├── NewsDrawer.tsx       # 右侧抽屉（详情）
│   │   ├── FavoriteButton.tsx
│   │   ├── DateSwitcher.tsx     # 日期切换（看历史）
│   │   └── ui/                  # shadcn 组件
│   ├── lib/
│   │   ├── api.ts               # 后端 API 封装
│   │   └── types.ts
│   ├── styles/globals.css
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── package.json
│   └── tsconfig.json
│
├── tasks/
│   ├── plan.md                  # 本文件
│   └── todo.md                  # 任务清单
│
├── .gitignore
└── README.md                    # 总入口（如何启动）
```

---

## 四、数据模型

### 表：sources（RSS 源，启动时从 yaml 同步）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| key | str unique | 源标识，如 `jiqizhixin` |
| name | str | 显示名 |
| url | str | RSS URL |
| use_proxy | bool | 是否走代理 |
| enabled | bool | 是否启用 |
| last_fetched_at | datetime | 最近拉取时间 |
| last_status | str | ok / failed / disabled |

### 表：raw_articles（拉取的原始候选）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| source_id | int FK | |
| guid | str | RSS 中的唯一标识，去重用 |
| title | str | |
| link | str unique | 原文 URL |
| published_at | datetime | |
| raw_summary | text | RSS 自带摘要 |
| full_text | text nullable | trafilatura 提取的正文 |
| fetched_at | datetime | |

唯一索引：`(source_id, guid)` 或 `link`。

### 表：news_items（AI 处理后的最终新闻，对外展示）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| date | date | 所属日期（YYYY-MM-DD） |
| category | str | 板块 key |
| importance | int | 0-100 重要度（仅后端排序用，前端不展示数值） |
| title | str | |
| summary | str | 一句话摘要 |
| full_summary | text | 详细总结 |
| viewpoints | json | 观点列表 [{view, source}] |
| background | text | 背景补充 |
| source_links | json | [{name, url}] 原文来源 |
| raw_article_id | int FK | 主原文（可空） |
| created_at | datetime | |

索引：`(date, category, importance desc)`。

### 表：favorites（收藏）
| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| news_item_id | int FK unique | |
| favorited_at | datetime | |

不分用户（单人使用）。

---

## 五、API 设计

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/categories` | 板块清单（含每板块今日条数） |
| GET | `/api/news?date=YYYY-MM-DD&category=xxx` | 某日某板块的 6 条 |
| GET | `/api/news/{id}` | 详情（含全部字段） |
| GET | `/api/favorites` | 收藏列表（分页，最新优先） |
| POST | `/api/favorites` body: `{news_item_id}` | 收藏 |
| DELETE | `/api/favorites/{news_item_id}` | 取消收藏 |
| POST | `/api/admin/refresh` | 手动触发拉取（兜底用，前端首次访问发现无数据时调用） |
| GET | `/api/admin/status` | 流水线状态：今日是否已生成、上次运行时间、各源状态 |

---

## 六、AI 流水线设计（核心）

每日 8:00 触发 `orchestrator.run_daily()`：

```
[1] fetch_all_sources()
    └─ 并发拉取所有 enabled 源（海外源走代理，国内直连）
    └─ 失败源：记录日志、标记 last_status=failed，跳过
    └─ 输出：候选 raw_articles（去重：source_id+guid 或 link）

[2] filter_by_time()
    └─ 只保留过去 24h（published_at >= now-24h）

[3] classify_and_score()  ← LLM 调用 1
    └─ 批量送入：每批 30-50 条标题+RSS摘要
    └─ Prompt：让模型对每条返回 {category, importance, keep}
       - category: 10 个板块 key 之一 或 "其他"
       - importance: 0-100
       - keep: bool（明显不相关、低质、广告标 false）
    └─ 输出：带 category 和 importance 的候选列表

[4] select_top_per_category()
    └─ 每板块按 importance desc 取 top 8（多取 2 条作为容错）

[5] extract_full_text()
    └─ 对入选的约 80 条，用 trafilatura 抓正文（带代理）
    └─ 失败的降级用 raw_summary

[6] summarize()  ← LLM 调用 2
    └─ 单条调用：输入正文，输出 {summary, full_summary, viewpoints[], background}
    └─ 失败的：跳过（导致该板块少于 6 条时从备选 2 条补）

[7] persist()
    └─ 写入 news_items 表，date=今天
    └─ 每板块最多 6 条
```

**Prompt 设计要点**（详见各模块代码）：
- 分类阶段强调"跨领域归入相关度最高的单一板块"
- 摘要阶段要求"客观中立、突出关键事实、观点要标注信息来源"

**成本控制**：
- 分类批量化（一次几十条）减少请求数
- 摘要单条调用，使用 system prompt 的缓存
- 整体每日成本约 ¥1（前面已估算）

---

## 七、依赖图（顶层）

```
[配置] sources.yaml + categories.yaml
   ↓
[基础设施] db.py / models.py / config.py / utils
   ↓
[流水线] fetcher → extractor → classifier → summarizer → orchestrator
   ↓
[调度] scheduler.py（8:00 + 兜底）
   ↓
[API] news / favorites / admin
   ↓
[前端基础] layout / globals / tailwind / shadcn 安装
   ↓
[前端组件] CategoryTabs → NewsCard → NewsDrawer → FavoriteButton → DateSwitcher
   ↓
[前端页面] page.tsx → favorites/page.tsx
   ↓
[联调] 端到端验证
```

---

## 八、垂直切片任务（每个 Task = 一条完整可验证的路径）

为避免横向"先把所有后端写完再写前端"的反模式，按"垂直切片"切分：每个 Task 都打通从配置到展示的最小可工作链路，逐步加宽。

### Phase 0：脚手架（让两端都能跑起来）
- **T01** 项目脚手架与目录初始化
- **T02** 后端 hello world：FastAPI + SQLite + 配置加载
- **T03** 前端 hello world：Next.js + Tailwind + shadcn 初始化

🔍 **Checkpoint A**：前后端各自能 `npm run dev` / `uvicorn` 启动，前端能调通 `/api/health`。

### Phase 1：单源端到端（最小可工作产品）
- **T04** RSS 配置文件 + 单源拉取（机器之心，国内不走代理）
- **T05** 数据库模型 + 写入 raw_articles
- **T06** trafilatura 正文提取
- **T07** LLM 客户端封装 + 摘要功能（单条）
- **T08** API：`/api/news` 返回硬编码板块、单源、当日数据
- **T09** 前端：单板块卡片列表 + 详情抽屉（最丑能看版）

🔍 **Checkpoint B**：手动触发一次，能在网页上看到机器之心当天的新闻卡片，点击展开详情看到 AI 摘要。

### Phase 2：完整流水线
- **T10** 全部 RSS 源接入 + 代理支持 + 失败容错
- **T11** AI 分类 + 重要度评分（批量）
- **T12** 流水线编排（orchestrator）+ 每板块 6 条选择逻辑
- **T13** APScheduler 8:00 定时任务 + 启动兜底检查
- **T14** `/api/admin/refresh` 与 `/api/admin/status`

🔍 **Checkpoint C**：手动触发一次完整流水线，10 个板块各 6 条都生成成功，日志清晰。第二天 8:00 自动跑通。

### Phase 3：完整 UI
- **T15** 顶部板块 Tab + 板块切换
- **T16** 卡片样式精修（Linear 风格，留白、字体层级、hover 微动效）
- **T17** 抽屉详情：摘要/总结/观点/背景/来源链接 完整呈现
- **T18** 收藏功能：按钮、API、收藏列表页
- **T19** 日期切换器（看历史日期）
- **T20** 移动端响应式 + 加载/空状态/错误态

🔍 **Checkpoint D**：在 PC 和手机（同局域网）打开网页，板块切换、阅读、收藏、看历史日期都流畅。

### Phase 4：打磨与文档
- **T21** 端到端冒烟测试（pytest + 简单前端手工脚本）
- **T22** README：启动步骤、配置说明、常见问题（VPN 端口、API key、依赖安装）
- **T23** 兜底首次访问触发拉取的体验优化（loading 状态）

🔍 **Checkpoint E**：陌生人按 README 能在一台干净的 Windows 上跑起来。

---

## 九、Acceptance Criteria（每个 Phase 的总验收）

### Phase 0
- 后端 `GET /api/health` 返回 `{"ok": true}`
- 前端首页能展示一个"Hello"卡片
- 两端能跨域通信（CORS 配好）

### Phase 1
- 配置文件指定 1 个源 → 拉取 → 写入 db → AI 摘要 → API 返回 → 前端卡片展示 → 抽屉看详情，全链路打通
- 失败任一步骤有明确日志

### Phase 2
- 10 个板块全部有数据，每板块 ≤ 6 条
- 跨领域新闻只出现在最高相关度板块
- 海外源能通过代理拉到（验证：BBC 至少有 1 条国际新闻进入流水线）
- 8:00 自动跑通（可通过临时改 cron 到 1 分钟后验证）
- 兜底：清空当日数据、刷新页面 → 触发拉取 → 完成后展示

### Phase 3
- 10 个板块切换流畅，无白屏
- 卡片视觉达到"简洁高级"标准（具体见 T16 acceptance）
- 收藏跨设备同步生效（PC 收藏，手机刷新能看到）
- 移动端可正常使用

### Phase 4
- README 完整可复现
- 单日 API 成本 ≤ ¥2

---

## 十、技术风险与应对

| 风险 | 概率 | 应对 |
|---|---|---|
| 部分 RSS 源失效或改版 | 高 | 启动时探测，失效源自动 disable，日志告警，不阻塞流水线 |
| 海外源即使有代理也慢/超时 | 中 | 设置合理 timeout（10s），失败重试 1 次，再失败跳过 |
| AI 大模型 API 偶发失败 | 中 | 单条摘要失败不影响整体，最多导致某板块 < 6 条 |
| trafilatura 提取不到正文 | 中 | 降级使用 raw_summary（RSS 自带摘要） |
| 8:00 电脑没开机 | 必然 | 启动时检查今日是否已生成，未生成且首次访问时触发；APScheduler 用 `misfire_grace_time` 设大一些 |
| AI 分类不准导致板块倾斜 | 中 | Prompt 中给出板块定义和示例；importance 阈值过滤；监控每板块条数 |
| SQLite 并发写 | 低 | 单人使用 + WAL 模式，不会有问题 |
| 跨设备访问需局域网 | 已知 | README 写清"启动后访问 http://你电脑IP:3000"；后续可迁云服务器 |

---

## 十一、不在本计划范围内（明确不做）

- 用户系统、登录、多用户隔离
- 推送通知（邮件/IM）
- 评论、分享、社交功能
- 全文搜索（之后可加）
- 深度阅读模式 / 朗读 / 翻译
- Docker / K8s / CI/CD（个人本机用不上）
- 单元测试 100% 覆盖（关键路径有冒烟测试即可）

---

## 十二、预期工期

按你独立完成估算（我提供代码，你执行命令并 review）：

- Phase 0：1-2 小时
- Phase 1：3-4 小时（首次跑通最关键）
- Phase 2：4-6 小时
- Phase 3：4-6 小时
- Phase 4：1-2 小时

**合计约 13-20 小时**，可分 3-5 个工作时段完成。每个 Checkpoint 都是天然的暂停点。
