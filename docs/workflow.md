# 每日新闻早报网站 - 工作流程详解

## 项目概述

这是一个自动化的每日新闻聚合系统，从全球 RSS 源抓取新闻，通过 AI 进行分类和摘要，为用户提供按板块整理的新闻早报。

### 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          用户浏览器                              │
│                     http://localhost:3000                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Next.js 前端                               │
│            轮询 /api/admin/status 获取进度                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI 后端                               │
│                   http://localhost:8000                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     流水线（7 步流程）                            │
│   fetch → filter → classify → select → extract → summarize → persist
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │ RSS 源  │     │  LLM   │     │ SQLite  │
        │ (37个)  │     │DeepSeek│     │  数据库  │
        └─────────┘     └─────────┘     └─────────┘
```

---

## 完整工作流程

系统每日北京时间 08:00 自动执行以下 7 个步骤：

```
步骤1        步骤2        步骤3        步骤4        步骤5        步骤6        步骤7
RSS抓取  →  日期过滤  →  AI分类   →  选择Top-8 →  全文提取  →  AI摘要   →  写入数据库
(60秒)      (<1秒)      (10分钟)     (<1秒)      (2分钟)     (9分钟)     (<1秒)
```

---

## 步骤 1：RSS 源抓取

### 目标

从 37 个 RSS 源拉取最近 24 小时的文章。

### 输入

数据库中所有 `enabled=True` 的 RSS 源：

```yaml
# backend/config/sources.yaml 示例
- name: "36氪"
  url: "https://36kr.com/feed"
  use_proxy: false
  enabled: true

- name: "TechCrunch AI"
  url: "https://techcrunch.com/category/artificial-intelligence/feed/"
  use_proxy: true
  enabled: true
```

### 处理过程

```
37 个 RSS 源
    │
    ↓ 异步并发抓取（semaphore=10，最多 10 个并发）
    │
    ├─→ 36kr/feed → 解析 RSS → 提取 25 篇
    ├─→ techcrunch/feed → 解析 RSS → 提取 20 篇
    ├─→ arxiv/cs.AI → 解析 RSS → 提取 480 篇
    ├─→ ...
    └─→ bbc/news → 解析 RSS → 提取 36 篇
    │
    ↓ 去重（基于 source_id + guid）
    │
    ↓ 保存到 raw_articles 表
```

### 输出

`raw_articles` 表中的原始文章记录：

| 字段 | 示例值 | 说明 |
|------|--------|------|
| id | 1234 | 自增主键 |
| source_id | 1 | 来源 ID |
| guid | "abc-123" | 文章唯一标识 |
| title | "OpenAI 发布 GPT-5" | 标题 |
| link | "https://..." | 原文链接 |
| raw_summary | "OpenAI 今日宣布..." | RSS 中的摘要 |
| published_at | 2026-05-11 08:30 | 发布时间 |

---

## 步骤 2：日期过滤

### 目标

筛选出最近 24 小时内的文章，剔除过期内容。

### 输入

`raw_articles` 表中的所有文章。

### 处理过程

```python
# 时间窗口计算
now_cst = 当前北京时间
day_start = now_cst - 24小时
day_end = now_cst

# 过滤条件
candidates = raw_articles WHERE published_at >= day_start AND published_at < day_end
```

**分界点规则**：
- 08:00 前执行 → 筛选前一天的文章
- 08:00 后执行 → 筛选当天的文章

### 输出

符合时间条件的候选文章列表（约 1000-1500 条）。

---

## 步骤 3：AI 分类与重要性评分

### 目标

使用 LLM 对每篇文章进行分类（8 个板块之一）和重要性评分（0-100 分）。

### 输入

**System Prompt**（定义分类规则）：

```
你是一位资深新闻编辑，负责新闻的分类与价值评估。

板块分类标准：
- ai: 大语言模型、多模态AI、AI产品发布、算法突破
- tech: 消费电子产品、硬件设备、软件应用、技术趋势
- internet: 互联网公司动态、平台运营策略、社交网络、电商
- finance: 股市行情、投资机构动向、宏观经济政策、加密货币
- business: 企业战略、商业模式创新、产业格局变化
- international: 地缘政治、国际关系、重大外交事件、战争冲突
- ai_paper: AI领域最新学术论文、实验室突破、算法进展
- social: 社会热点事件、民生问题、文化现象、教育变革

重要性评估规则：
【AI 与大模型】
  - 高（80-100）：GPT级别模型发布、重大算法突破
  - 中（50-79）：AI产品更新、开源模型发布
  - 低（0-49）：常规资讯、一般性报道

过滤规则（keep=false）：
- 明显广告、软文、招聘、活动预告
- 标题党但内容空洞
- 重复报道同一事件且无新增信息

输出格式：JSON 数组
```

**User Prompt**（每批 60 条新闻）：

```json
[
  {"id": 123, "title": "OpenAI发布GPT-5", "summary": "OpenAI今日宣布..."},
  {"id": 124, "title": "苹果WWDC2026", "summary": "苹果在开发者大会上..."},
  {"id": 125, "title": "特斯拉Q1财报超预期", "summary": "特斯拉公布..."}
]
```

### 处理过程

```
1000-1500 条候选文章
    │
    ↓ 分批（每批 60 条）
    │
    ├─→ 批次1: 60条 → 调用 LLM → 返回分类结果
    ├─→ 批次2: 60条 → 调用 LLM → 返回分类结果
    ├─→ ...
    └─→ 批次N: 60条 → 调用 LLM → 返回分类结果
    │
    ↓ 更新数据库中的 category 和 importance 字段
```

**LLM 输出示例**：

```json
[
  {"id": 123, "category": "ai", "importance": 95, "keep": true},
  {"id": 124, "category": "tech", "importance": 80, "keep": true},
  {"id": 125, "category": "finance", "importance": 70, "keep": true}
]
```

### 输出

每篇文章获得：
- `category`：所属板块（ai/tech/internet/finance/business/international/ai_paper/social/other）
- `importance`：重要性分数（0-100）

---

## 步骤 4：选择 Top-8 新闻

### 目标

每个板块按重要性排序，选取前 8 名进入后续处理。

### 输入

步骤 3 分类后的所有候选文章。

### 处理过程

```python
# 按板块分组
category_pools = {
    "ai": [],
    "tech": [],
    "internet": [],
    ...
}

# 将文章分配到对应板块
for art in candidates:
    if art.category in CATEGORIES:
        category_pools[art.category].append(art)

# 每个板块按 importance 降序排序，取前 8
for cat in CATEGORIES:
    category_pools[cat].sort(key=lambda a: a.importance, reverse=True)
    category_pools[cat] = category_pools[cat][:8]  # TOP_PER_CATEGORY = 8
```

**示例**（ai 板块）：

| 排名 | 标题 | importance |
|------|------|------------|
| 1 | DeepSeek 发布 V3 模型 | 95 |
| 2 | OpenAI 推出 GPT-5 | 92 |
| 3 | Google Gemini 2.0 发布 | 88 |
| ... | ... | ... |
| 8 | Hugging Face 新增 1000 个模型 | 75 |

### 输出

每个板块的 Top-8 候选文章（共约 60-64 篇）。

**为什么取 8 而不是 6？**
保留冗余，防止后续摘要生成失败时没有备用文章。

---

## 步骤 5：全文提取

### 目标

获取文章的完整正文内容，用于生成更准确的摘要。

### 输入

步骤 4 选出的 Top-8 文章（约 60-64 篇）。

### 处理过程

```
60-64 篇文章
    │
    ↓ 遍历每篇文章
    │
    ├─→ 检查是否已有 full_text → 有则跳过
    │
    ├─→ 使用 trafilatura 抓取网页内容
    │   │
    │   ├─→ 成功 → 保存 full_text
    │   └─→ 失败 → 使用 raw_summary 作为备用
    │
    ↓ 提交数据库
```

**提取失败的常见原因**：

| 错误类型 | 示例网站 | 原因 |
|----------|----------|------|
| 403 Forbidden | Bloomberg, FT | 付费墙 |
| 404 Not Found | 已删除文章 | 链接失效 |
| SSL Error | 部分网站 | 证书问题 |
| 超时 | 网络问题 | 连接不稳定 |

### 输出

每篇文章获得 `full_text` 字段（完整正文或原始摘要）。

---

## 步骤 6：AI 摘要生成

### 目标

为每篇文章生成结构化摘要，包括一句话摘要、详细总结、观点提炼和背景补充。

### 输入

**System Prompt**（定义摘要规则）：

```
你是一位专业新闻编辑，负责对新闻进行摘要、总结和观点提炼。

输出严格的 JSON 格式：
{
  "summary": "一句话摘要（30字以内，突出最核心事实）",
  "full_summary": "详细总结（100-200字，客观中立，涵盖关键事实、数据、影响）",
  "viewpoints": [
    {"view": "某方观点或影响判断", "source": "信息来源"}
  ],
  "background": "背景补充（50-100字）"
}

核心原则——真实性是新闻的生命线：
1. 所有内容必须严格基于原文，禁止编造、杜撰、推测
2. 原文没有提到的信息，绝对不能自行添加
3. 信息不足时宁可留空也不要虚构
4. 全部使用中文
```

**User Prompt**（单篇文章）：

```
标题：DeepSeek 发布 V3 模型，性能超越 GPT-4o

正文：中国 AI 公司 DeepSeek 今日正式发布其最新大语言模型 V3...
（最多 3000 字符）
```

### 处理过程

```
60-64 篇文章
    │
    ↓ 并发处理（5 个线程）
    │
    ├─→ 文章1: title + full_text → 调用 LLM → 返回摘要
    ├─→ 文章2: title + full_text → 调用 LLM → 返回摘要
    ├─→ ...
    └─→ 文章N: title + full_text → 调用 LLM → 返回摘要
    │
    ↓ 存储到 summary_results 字典
```

**LLM 输出示例**：

```json
{
  "summary": "DeepSeek发布V3模型，多项基准测试超越GPT-4o",
  "full_summary": "中国AI公司DeepSeek正式发布其最新大语言模型V3，该模型在多项基准测试中表现优异，超越了OpenAI的GPT-4o。V3采用混合专家架构，参数量达到670B，在代码生成、数学推理等任务上展现出强大能力。此举标志着中国在大模型领域的重大突破。",
  "viewpoints": [
    {"view": "中国AI技术正在快速追赶美国", "source": "行业分析师"},
    {"view": "开源模型将加速AI技术普及", "source": "DeepSeek CTO"}
  ],
  "background": "DeepSeek成立于2023年，是一家专注于大语言模型研发的中国AI公司。此前发布的V2模型已在开源社区获得广泛关注。"
}
```

### 输出

每篇文章获得：
- `summary`：一句话摘要
- `full_summary`：详细总结
- `viewpoints`：观点列表
- `background`：背景补充

---

## 步骤 7：写入数据库

### 目标

将最终结果保存到 `news_items` 表，每板块保留前 6 条。

### 输入

步骤 6 生成的摘要结果 + 步骤 4 的 Top-8 文章。

### 处理过程

```python
FINAL_PER_CATEGORY = 6  # 每板块最终保留 6 条

for cat, pool in category_pools.items():
    written = 0
    for art in pool:
        if written >= 6:  # 达到上限
            break

        result = summary_results.get(art.id)
        if result is None:  # 摘要失败，跳过
            continue

        # 写入 news_items 表
        item = NewsItem(
            date=target_date,
            category=cat,
            importance=art.importance,
            title=art.title,
            summary=result["summary"],
            full_summary=result["full_summary"],
            viewpoints=result["viewpoints"],
            background=result["background"],
            source_links=[{"name": source_name, "url": art.link}],
        )
        db.add(item)
        written += 1

    db.commit()
```

**示例**（ai 板块）：

| 最终排名 | 标题 | importance | 状态 |
|----------|------|------------|------|
| 1 | DeepSeek 发布 V3 模型 | 95 | ✅ 写入 |
| 2 | OpenAI 推出 GPT-5 | 92 | ✅ 写入 |
| 3 | Google Gemini 2.0 发布 | 88 | ✅ 写入 |
| 4 | Anthropic Claude 4 发布 | 85 | ✅ 写入 |
| 5 | Meta 开源 Llama 4 | 82 | ✅ 写入 |
| 6 | 百度文心一言 5.0 | 78 | ✅ 写入 |
| 7 | 某 AI 创业公司融资 | 75 | ❌ 跳过（达到上限） |
| 8 | AI 伦理研讨会 | 72 | ❌ 跳过（达到上限） |

### 输出

`news_items` 表中的最终新闻记录：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | DATE | 新闻日期 |
| category | VARCHAR | 板块分类 |
| importance | INTEGER | 重要性分数（0-100） |
| title | VARCHAR | 标题 |
| summary | TEXT | 一句话摘要 |
| full_summary | TEXT | 详细总结 |
| viewpoints | JSON | 观点列表 |
| background | TEXT | 背景补充 |
| source_links | JSON | 来源链接 |

---

## 8 个新闻板块

| 板块 | 名称 | 内容范围 | 高重要性示例 |
|------|------|----------|--------------|
| `ai` | AI 与大模型 | 大语言模型、多模态AI、AI产品发布、算法突破 | GPT级别模型发布、重大算法突破 |
| `tech` | 科技产业 | 消费电子、硬件设备、软件应用、技术趋势 | 新品类发布（如Vision Pro级别） |
| `internet` | 互联网 | 互联网公司动态、平台运营、社交网络、电商 | 巨头战略转型、重大并购 |
| `finance` | 金融投资 | 股市行情、投资机构、宏观经济、加密货币 | 市场重大波动、央行政策 |
| `business` | 商业与经济 | 企业战略、商业模式、产业格局、消费趋势 | 行业格局重塑、重大战略转型 |
| `international` | 国际时政 | 地缘政治、国际关系、外交事件、战争冲突 | 战争/和平进程、重大外交突破 |
| `ai_paper` | AI 前沿论文 | 学术论文、实验室突破、算法进展、学术会议 | 顶会最佳论文、颠覆性算法 |
| `social` | 社会人文 | 社会热点、民生问题、文化现象、教育变革 | 重大社会事件、广泛影响的政策 |

---

## 性能分析

### 各步骤耗时分布

```
步骤1: RSS抓取     ████ 60秒 (4.5%)
步骤2: 日期过滤     <1秒
步骤3: AI分类       ██████████████████████████████████████ 10分35秒 (47.3%)
步骤4: 选择新闻     <1秒
步骤5: 全文提取     ████ 2分3秒 (9.2%)
步骤6: AI摘要       ██████████████████████████ 8分45秒 (39.1%)
步骤7: 写入数据库   <1秒
```

### 瓶颈分析

| 步骤 | 瓶颈类型 | 原因 |
|------|----------|------|
| AI 分类 | LLM API 调用 | 并发 5 线程，每批 60 条 |
| AI 摘要 | LLM API 调用 | 并发 5 线程，每篇单独调用 |
| RSS 抓取 | 网络延迟 | 已是并发，受限于源服务器响应 |
| 全文提取 | 网络请求 | 已是并发，部分网站 403 拒绝 |

---

## 配置文件说明

### 环境变量（`backend/.env`）

```env
# LLM 配置
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat

# 代理配置（用于海外 RSS 源）
PROXY_URL=http://127.0.0.1:7897

# RSSHub（本地自建实例，提供无原生 RSS 的平台源）
RSSHUB_BASE_URL=http://localhost:1200
RSSHUB_AUTO_START=true

# 数据库
DATABASE_URL=sqlite:///./data/news.db
```

### RSS 源配置（`backend/config/sources.yaml`）

```yaml
# 国内源（不需要代理）
- key: 36kr
  name: "36氪"
  url: "https://36kr.com/feed"
  use_proxy: false
  enabled: true

# 海外源（需要代理）
- key: techcrunch_ai
  name: "TechCrunch AI"
  url: "https://techcrunch.com/category/artificial-intelligence/feed/"
  use_proxy: true
  enabled: true

# RSSHub 源（本地实例提供）
- key: zhihu_hot
  name: "知乎热榜"
  url: "${RSSHUB_BASE_URL}/zhihu/hot"
  use_proxy: false
  enabled: true
```

### 分类配置（`backend/config/categories.yaml`）

定义 8 个板块的名称和描述，需与代码中的 `CATEGORIES` 列表保持同步。

---

## API 接口

### 触发工作流

```bash
POST /api/admin/refresh
```

### 查看进度

```bash
GET /api/admin/status
```

返回示例：
```json
{
  "pipeline_running": true,
  "today_count": 0,
  "last_run": null,
  "progress": {
    "step": "AI 正在分类与评分...",
    "step_index": 3
  }
}
```

### 获取新闻列表

```bash
GET /api/news?date=2026-05-11&category=ai
```

### 获取板块列表

```bash
GET /api/categories
```

---

## 文件结构

```
backend/
├── app/
│   ├── api/
│   │   ├── admin.py          # 管理 API
│   │   ├── news.py           # 新闻 API
│   │   └── favorites.py      # 收藏 API
│   ├── pipeline/
│   │   ├── fetcher.py        # 步骤1: RSS 抓取
│   │   ├── classifier.py     # 步骤3: AI 分类
│   │   ├── extractor.py      # 步骤5: 全文提取
│   │   ├── summarizer.py     # 步骤6: AI 摘要
│   │   ├── orchestrator.py   # 流程编排
│   │   └── sync_sources.py   # 源同步
│   ├── rsshub.py             # RSSHub 生命周期管理
│   ├── models.py             # 数据库模型
│   ├── config.py             # 配置加载
│   └── scheduler.py          # 定时任务
├── config/
│   ├── sources.yaml          # RSS 源配置
│   └── categories.yaml       # 分类配置
└── .env                      # 环境变量
```
