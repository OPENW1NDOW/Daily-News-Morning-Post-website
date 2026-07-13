# X Following 板块设计（bird CLI）

日期：2026-07-13  
状态：待审阅  
范围：个人早报站增加「Following」板块，基于 bird 从 X 拉取已关注博主帖子

---

## 1. 背景与目标

个人用每日新闻早报已具备 RSS → LLM 分类摘要 → 分板块展示的主链路。Cooper 日常还关注一批 AI / Agent / LLM 向的 X 博主，希望在早报界面增加 **Following** 板块，收录这些账号当日值得看的帖子。

### 成功标准

- 每天与主早报同一调度周期内，能产出一个 `following` 板块（建议最多 8 条）
- 可在管理后台同步 X Following 名单，并勾选启用/停用账号
- bird / Cookie 失败时，主 RSS 早报仍正常；Following 旁路降级跳过并可见状态
- 不引入小红书；不做生产级社交监听

### 非目标（本版不做）

- 小红书或其他社交平台
- Cookie 自动续期 / 在后台网页里改 Cookie
- 把每个博主建模成现有 RSS `sources` 行
- 官方 X API 付费接入
- 热搜 / 全站趋势雷达

---

## 2. 已拍板决策

| 项 | 选择 |
|----|------|
| 产品形态 | 独立 Following 板块（非混入 AI 新闻） |
| 抓取工具 | bird（Cookie + X GraphQL） |
| 运行位置 | 腾讯云服务器，与现有流水线一起 |
| 账号来源 | 自动同步全部 Following + 后台勾选启停 |
| 帖子筛选 | 规则预过滤 + LLM 精选 |
| Cookie | `.env` 手动配置；续期以后再做 |
| 架构 | **流水线旁路**（方案 1）：主 RSS 七步不动 |

---

## 3. 架构

```
每日调度 / 手动 refresh
│
├─ 主线（现有）
│   fetch → filter → classify → select → extract → summarize → persist
│
└─ Following 旁路（best-effort，失败不阻断主线）
    load enabled x_accounts
      → bird 拉近 24h 帖
      → 规则过滤
      → LLM 精选 Top N
      → persist news_items (category=following)
```

前端从现有 `/api/news?category=following`（及 categories 列表）读取展示，复用 `NewsDrawer`。

---

## 4. 数据模型

### 4.1 新表 `x_accounts`

| 字段 | 说明 |
|------|------|
| `id` | PK |
| `x_user_id` | X 用户 ID（同步去重键） |
| `handle` | `@` 不含或含均可，入库统一不含 `@` |
| `display_name` | 展示名 |
| `avatar_url` | 可选 |
| `enabled` | 是否参与抓帖；**新同步账号默认 `true`** |
| `is_following` | 是否仍在 X Following 中；同步时维护 |
| `first_seen_at` | 首次同步时间 |
| `last_synced_at` | 最近一次出现在 Following 同步结果中的时间 |
| `updated_at` | 行更新时间 |

**同步语义（upsert）：**

- 仍在 Following 中 → 更新 handle / display_name / `last_synced_at`，设 `is_following=true`，**不覆盖** `enabled`
- 新出现 → insert，`enabled=true`，`is_following=true`
- 已不在 Following 中 → **不删行**，设 `is_following=false`；抓帖条件为 `enabled=true AND is_following=true`

### 4.2 复用 `raw_articles` / `news_items`

- 为 Following 建一条逻辑源或专用 `source`（例如 key=`x_following`），便于 `source_id + guid` 去重；guid = 推文 ID
- 最终展示写入 `news_items`：
  - `category = "following"`
  - `title`：推文首句或截断
  - `summary` / `full_summary`：LLM 短摘要（viewpoints/background 可空或简化）
  - `source_links`：至少包含原推 URL，并带 `@handle`
  - `importance`：可用 LLM 分或规则分，仅在 following 池内排序，不与新闻板块混排

### 4.3 配置

- `backend/config/categories.yaml` 增加：

```yaml
- key: following
  name: Following
  description: 你在 X 上关注的博主精选帖（AI / Agent / LLM 向）
```

- `classifier.CATEGORIES`（及任何硬编码板块列表）必须同步加入 `following`
- **注意**：RSS 文章的 LLM 分类 **不得** 把新闻分到 `following`；`following` 仅由旁路写入。分类 prompt 中应写明：`following` 不用于 RSS 分类（或分类器仍用原 8 类，旁路单独写 category）

推荐：**RSS 分类器保持现有 8 类不变**；`following` 只出现在 categories 展示列表与旁路 persist，避免污染分类。

### 4.4 环境变量

```
X_AUTH_TOKEN=...
X_CT0=...
# 可选
X_FOLLOWING_TOP_N=8
BIRD_BIN=bird   # 或 npx / 绝对路径
```

不入库、不进 git；管理后台只显示「已配置 / 缺失 / 最近旁路错误」。

---

## 5. 模块设计

### 5.1 `bird_client`

职责：封装对 bird CLI（或等价 Node 库调用）的调用。

- 从 settings 读 Cookie
- 能力：`list_following()`、`fetch_user_tweets(handle_or_id, since)`  
- 统一超时、非零退出、Cookie 失效错误类型
- 实现细节（CLI subprocess vs 库）在实现计划里选定；对外 Python API 稳定即可

依赖说明：原 `steipete/bird` 仓库已下架；以 npm `@steipete/bird` 或社区镜像为准，文档中记录安装方式与风险（非官方 GraphQL，可能随时失效）。

### 5.2 `sync_following`

- 调用 `list_following()` → upsert `x_accounts`
- 由管理后台「同步」按钮触发；也可在旁路开始时若名单为空则自动同步一次（可选，实现时可定）
- 不抓推文正文

### 5.3 `fetch_tweets`（旁路一步）

- 查询 `enabled=true` 的账号
- 逐个或有限并发拉近 24h 帖（与主早报「日界」一致：Asia/Shanghai）
- 归一字段：`guid, handle, text, link, published_at, is_retweet, is_quote, ...`

### 5.4 规则过滤

默认丢弃：

- 纯转发（无自己评语）
- 过短碎碎念（可配置最小字符数，如 40）
- 空内容 / 仅链接无文字（可保留「有实质评语 + 链接」的帖，实现时用简单启发式）

默认保留：

- 原创帖
- 带评语的引用转发（quote）

### 5.5 LLM 精选

- 输入：规则过滤后的候选（title/text 截断）
- 输出：每条 `keep`、短 `summary`、可选 `score`
- 偏好：AI / Agent / LLM / 行业实质信息；拒广告、无信息量日常
- 按 score/importance 取 Top N（默认 8）再摘要落库；若精选与摘要可合并为一次调用以省成本，实现计划可优化，行为不变

### 5.6 Orchestrator 集成

在现有 `run_pipeline` 中，主线成功路径末尾或并行阶段调用 `run_following_branch()`：

- try/except 包裹；异常只写 `pipeline_runs.result` 的 following 子状态 / 日志
- 清除当日旧 `news_items where category=following` 再写入（与主线按日覆盖语义一致）

---

## 6. API 与管理后台

### 6.1 Admin API（需管理员鉴权）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/x-following/accounts` | 列表（支持按 enabled 过滤） |
| PATCH | `/api/admin/x-following/accounts/{id}` | 更新 `enabled` |
| POST | `/api/admin/x-following/sync` | 触发同步 Following |
| GET | `/api/admin/x-following/status` | Cookie 是否配置、上次同步时间、上次旁路错误 |

### 6.2 前端 Admin

新 Tab「X Following」：

- 同步按钮 + 状态条（Cookie / 上次同步 / 上次错误）
- 账号表：handle、显示名、开关

### 6.3 公开读

沿用现有 categories + news API；`following` 出现在 `/api/categories` 中即可被首页拉取。

---

## 7. 前端展示

- 首页 Tab / `SectionBlock` 增加 Following（名称来自 categories.yaml）
- 卡片：摘要 + `@handle`；点击打开现有 `NewsDrawer`
- 外链跳转原推
- 无数据时板块可隐藏或显示空状态（与现有空板块行为对齐即可）

---

## 8. 错误处理与运维

| 情况 | 行为 |
|------|------|
| 未配置 Cookie | 旁路跳过；后台 status 显示缺失 |
| bird 调用失败 / 429 | 旁路跳过或部分账号失败继续；记录错误 |
| 某账号拉取失败 | 跳过该账号，不失败整旁路 |
| 同步失败 | 后台报错；不改现有 enabled 配置 |

运维：Cookie 过期后 SSH 更新 `.env` 并重启 backend 容器。

---

## 9. 测试计划

- `x_accounts` upsert：新号默认启用；再同步不覆盖 enabled
- 规则过滤单测（纯 RT / 短文本 / quote）
- orchestrator：mock bird 抛错时主线仍 success，result 含 following 失败信息
- admin API：启停、同步（mock client）
- 不强制 e2e 打真 X（个人环境手工验证一次即可）

---

## 10. 风险

- bird / X GraphQL 非官方，可能突然不可用或导致账号风控——接受为个人项目风险
- 原仓库下架，依赖 npm/镜像版本钉死并在 README/SESSION 记录
- Following 量大时串行拉取变慢：限制并发（如 3）并只拉 enabled

---

## 11. 实现顺序（供后续 plan 拆解）

1. 模型 + categories 展示（classifier 不纳入 following）
2. `bird_client` + env + 本地/服务器安装说明
3. sync + admin API/UI
4. 旁路：fetch → 规则 → LLM → persist
5. 前端板块展示
6. 测试与 SESSION_LOG

---

## 12. 开放细节（实现时可定，不阻断本 spec）

- Top N 默认 8，可用 env 覆盖
- 最小正文字符数默认 40
- 是否在名单为空时自动 sync 一次
- bird 用全局 CLI 还是项目内 `npx`
