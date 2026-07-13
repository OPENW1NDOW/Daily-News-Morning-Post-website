# X Following 板块设计（bird CLI）

日期：2026-07-13  
状态：待审阅（doubt-driven 修订后）  
范围：个人早报站增加「Following」板块（bird）+ 同日重跑流水线时收藏不断（persist upsert）

---

## 1. 背景与目标

个人用每日新闻早报已具备 RSS → LLM 分类摘要 → 分板块展示的主链路。Cooper 日常还关注一批 AI / Agent / LLM 向的 X 博主，希望在早报界面增加 **Following** 板块，收录这些账号当日值得看的帖子。

同日多次跑流水线时，现有「先删当天 `news_items` 再插入」会导致 `favorites.news_item_id` 失效；本次一并改为 **按稳定键 upsert**，主线与 Following 共用该落库语义。

### 成功标准

- 与主早报同一调度周期内产出 `following` 板块（候选最多 8，落库 6，与主线一致）
- 管理后台可同步 X Following 并勾选启停
- bird / Cookie 失败不阻断主 RSS；主 RSS 失败也不阻断 Following（二者互不影响）
- 同日重跑流水线后，已收藏条目仍可打开（id 保持）
- 不引入小红书；不做生产级社交监听

### 非目标（本版不做）

- 小红书或其他社交平台
- Cookie 自动续期 / 在后台网页里改 Cookie
- 把每个博主建模成 RSS `sources.yaml` 行
- 官方 X API 付费接入
- 热搜 / 全站趋势雷达
- 收藏改存内容指纹（方案 C）

---

## 2. 已拍板决策

| 项 | 选择 |
|----|------|
| 产品形态 | 独立 Following 板块 |
| 抓取工具 | bird（Cookie + X GraphQL） |
| 运行位置 | 腾讯云服务器，与现有调度一起 |
| 账号来源 | 同步全部 Following + 后台勾选启停 |
| 帖子筛选 | 规则预过滤 + LLM 精选 |
| Cookie | `.env` 手动；续期以后再做 |
| 架构 | 流水线旁路；与主线**串行且互不拖死** |
| 条数 | 与主线一致：候选 Top **8** → 落库 **6** → API `limit(6)` |
| Hero | **排除** `category=following` |
| 时间窗 | **对齐主线** `target_date` + 北京时间 08:00 cutoff |
| 收藏 | 方案 **A**：稳定键 upsert；掉出 Top6 但仍被收藏的行**保留** |
| Docker | backend 镜像内安装 Node + 钉死 bird（或等价可调用二进制） |

---

## 3. 架构

```
每日调度 / 手动 refresh（同一 run_daily）
│
├─ 主线 RSS（try/except 独立）
│   fetch → filter → classify → select → extract → summarize
│   → persist_upsert(news categories)   # 不再 Step0 全日硬删
│
└─ Following 旁路（独立 try/except；主线成败都执行）
    load accounts (enabled AND is_following)
      → bird 按主线日界拉帖
      → 规则过滤
      → LLM 精选（候选≤8）
      → persist_upsert(category=following，最多 6 条)
```

约定：

- **禁止**与主线并行写同一天的 `news_items` 清理逻辑互相踩踏；旁路在主线 attempt **之后**串行执行（主线抛错也进入旁路）
- 进度：主线仍按现有 7 步；Following 单独写入 `pipeline_runs.result["following"]` 子对象，不把 `following` 计入 `classifier.CATEGORIES` / `total_categories`

前端：`/api/categories` + `/api/news?category=following`；Hero 选取时跳过 `following`。

---

## 4. 数据模型

### 4.1 新表 `x_accounts`

| 字段 | 说明 |
|------|------|
| `id` | PK |
| `x_user_id` | X 用户 ID，**UNIQUE**，同步去重键 |
| `handle` | 入库统一不含 `@` |
| `display_name` | 展示名 |
| `avatar_url` | 可选 |
| `enabled` | 是否允许抓帖；新号默认 `true`；同步**不覆盖** |
| `is_following` | 是否仍在 Following 中 |
| `first_seen_at` / `last_synced_at` / `updated_at` | 时间戳 |

**同步语义（须在事务内完成，避免半截把全表打成 `is_following=false`）：**

1. 先完整拉取 Following 列表到内存  
2. 成功后再 upsert：在列表中 → 更新资料、`is_following=true`（不改 `enabled`）；新号 → insert（`enabled=true`）  
3. 不在列表中 → `is_following=false`（不删行）  
4. 拉取失败 → **不改**任何 `is_following` / `enabled`

**抓帖条件：** `enabled=true AND is_following=true`（全文唯一口径）。

### 4.2 Following 与 `raw_articles`

**本版推荐：推文不入 `raw_articles`**，避免进入主线「时间窗全表 classify」。

- 旁路直接产出待写入的 following 条目（内存/临时结构）
- 稳定键见 §4.4；`guid` / 推文 ID 存在 `source_links` 或专用字段（实现可用 `news_items` 扩展 JSON，或加可空 `external_id` 列——`create_all` 对**新列**无效，故优先用现有 JSON/`raw_article_id` 为空 + `source_links` 内 `external_id`）

若实现时仍想落 `raw_articles`：必须专用 `Source.key=x_following`，且主线候选查询 **排除** 该 `source_id`（见 §4.3）。

### 4.3 逻辑源 `x_following`（仅当需要 raw_articles 时）

- **代码 seed**，不进 `sources.yaml`（避免 `sync_sources` 覆盖）
- `enabled=False` 恒成立；RSS fetch **跳过** `key==x_following`
- `url` 占位即可

### 4.4 `news_items` 写入与收藏安全 upsert

废除「Step 0：删除当天全部 `news_items`」。改为：

**稳定键**

| 类型 | 键 |
|------|----|
| RSS 新闻 | `(date, raw_article_id)`（`raw_article_id` NOT NULL） |
| Following | `(date, category='following', external_id=tweet_id)`（tweet_id 放在 `source_links` 约定字段或等价处，查询时解析；实现计划可加 UNIQUE 表达式/辅助列若可接受手工迁移） |

**行为**

1. 对本次应展示的集合（每板块最多 6 条 / following 最多 6 条）：存在则 **UPDATE** 标题摘要等，**保留 id**；不存在则 INSERT  
2. 当天该 category 下、不在新集合中的行：  
   - 若存在 `favorites` → **保留行**（早报列表不展示；靠查询「当日 Top 集合」或 importance/标记区分——实现上：列表 API 仍按 importance 取 Top6，被挤出但仍收藏的行留在 DB，仅出现在收藏页）  
   - 若不存在收藏 → DELETE（并可顺带确认无 orphan favorites）  
3. 同日重跑：同一文章/推文命中稳定键 → id 不变 → 收藏不断  

**Canonical URL（Following）**  
统一写成 `https://x.com/i/status/{tweet_id}`，避免 `twitter.com` / 带 query 的链接撞 `RawArticle.link` 或展示混乱。

**`source_links` 形状（兼容现前端）**

```json
[{ "name": "@handle", "url": "https://x.com/i/status/123" }]
```

可选同对象加 `"external_id": "123"`（前端可忽略未知字段）。

### 4.5 配置

在既有 `categories.yaml` 的 `categories:` **列表下追加**（不要改成裸 list）：

```yaml
categories:
  # …existing…
  - key: following
    name: Following
    description: 你在 X 上关注的博主精选帖（AI / Agent / LLM 向）
```

**硬性约定：**

- **`classifier.CATEGORIES` 不加 `following`**（保持现有 8 类）
- `following` 仅由旁路写入 `news_items.category`
- 展示列表来自 `categories.yaml`（`/api/categories`）

### 4.6 环境变量

```
X_AUTH_TOKEN=...
X_CT0=...
# 可选；候选上限，默认 8；最终落库固定 6（与 FINAL_PER_CATEGORY 对齐）
X_FOLLOWING_CANDIDATE_TOP_N=8
BIRD_BIN=bird
```

---

## 5. 模块设计

### 5.1 `bird_client`

- 读 Cookie；`list_following()`、`fetch_user_tweets(...)`
- 统一超时 / Cookie 失效错误类型
- 依赖：npm `@steipete/bird` 或社区镜像，**版本钉死**；Dockerfile 安装 Node 后全局或镜像内路径可调用
- 512M 内存：bird **串行或并发≤2**，避免与主线 LLM 峰值叠加 OOM

### 5.2 `sync_following`

- 后台「同步」触发；名单为空时旁路可自动 sync 一次（实现时做）
- 事务语义见 §4.1

### 5.3 `fetch_tweets`

- 账号：`enabled AND is_following`
- 时间：与主线同一 `day_start` / `day_end` / `target_date`（不是另起「滚动 24h」口径）
- 字段：`tweet_id, handle, text, link(canonical), published_at, is_retweet, is_quote`

### 5.4 规则过滤

丢弃：纯转发、过短（默认少于 40 字符）、空内容。  
保留：原创、带评语的 quote。

### 5.5 LLM 精选

- 输出 `keep` / `summary` / `score`
- 候选按分取 ≤8，再取 ≤6 条 upsert
- 偏好 AI/Agent/LLM 有信息量内容

### 5.6 Orchestrator（`run_daily` / `_run_daily_async`）

1. 去掉「删除当天全部 news_items」的 Step 0（改为各 persist 路径 upsert + 条件删除）  
2. 主线包在独立 try/except  
3. **无论主线成功与否**，再跑 Following 旁路（独立 try/except）  
4. `pipeline_runs.result` 形状示例：

```json
{
  "ai": 6,
  "tech": 6,
  "following": { "status": "ok", "written": 6, "error": null }
}
```

主线失败时 RSS 计数字段可缺省或为 0；`status` 字段：整 run 在「主线或旁路至少一侧有严重错误」时的取值在实现计划里定（建议：`success` 若主线 OK，旁路失败只记在 `following.error`；两侧都挂才 `error`——个人站优先可读）。

5. Admin progress：不把 following 算进 `categories_done`；可选 `following_step` 文案

---

## 6. API 与管理后台

### 6.1 Admin（需管理员）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/x-following/accounts` | 列表 |
| PATCH | `/api/admin/x-following/accounts/{id}` | 更新 `enabled` |
| POST | `/api/admin/x-following/sync` | 同步 Following |
| GET | `/api/admin/x-following/status` | Cookie 是否配置；上次同步时间；上次旁路错误（读最近 `pipeline_runs.result.following` 或专用状态行，**须持久化**，不能只靠进程内存） |

### 6.2 前端 Admin

Tab「X Following」：同步、状态条、启停列表。

### 6.3 公开读

- categories 含 following  
- news `limit(6)` 不变  
- Hero：全站最高 importance 时 **排除** `following`

---

## 7. 前端展示

- Following 分区 / Tab；卡片摘要 + `@handle`（来自 `source_links[0].name`）  
- `NewsDrawer`；`viewpoints`/`background` 可空，前端须容忍 null  
- 空板块行为对齐现有

---

## 8. 错误处理与运维

| 情况 | 行为 |
|------|------|
| 无 Cookie | 旁路跳过；status 显示缺失 |
| bird 失败 / 429 | 旁路失败记 result；主线不受影响 |
| 单账号失败 | 跳过该账号 |
| 同步失败 | 不改 enabled / is_following |
| 主线失败 | 仍跑旁路 |
| Cookie 更新 | 改 `.env` 后重启 backend 容器 |

---

## 9. 测试计划

- `x_accounts` upsert / 同步失败不污染 is_following  
- 规则过滤单测  
- **persist upsert**：同日二次写入同一 `raw_article_id` / tweet_id → id 不变；favorites 仍有效  
- 掉出 Top6 且有收藏 → 行保留；列表 Top6 不含它，收藏页含它  
- 主线 mock 失败时旁路仍执行；bird mock 失败时主线仍 success  
- admin sync / 启停  
- 不强制真 X e2e（手工一次）

---

## 10. 风险

- bird / GraphQL 非官方，可能失效或风控  
- 镜像需含 Node，体积与 512M 内存需注意  
- SQLite 无迁移：`x_accounts` 新表可用 `create_all`；若为 following 稳定键加物理 UNIQUE 列，需文档说明手工迁移或仅用应用层去重（个人项目可接受应用层 + 测试锁语义）

---

## 11. 实现顺序

1. **Persist upsert + 去掉全日 Step0 硬删**（收藏修复，可先合主线）  
2. Hero 排除 following；categories.yaml 追加 following（classifier 不动）  
3. `x_accounts` + bird_client + Docker Node/bird  
4. sync + admin API/UI  
5. 旁路 fetch → 规则 → LLM → upsert  
6. 前端 Following 展示  
7. 测试与 SESSION_LOG  

---

## 12. 仍可实现期微调（非 blocker）

- 最小正文字符数默认 40  
- 空名单是否自动 sync  
- `BIRD_BIN` 绝对路径 vs PATH 上的 `bird`  
- `pipeline_runs` 整 run 的 success/error 与旁路失败的精确组合规则（§5.6 已给建议默认）
