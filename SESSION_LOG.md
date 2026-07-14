# Session Log

每次 Claude Code session 完成重要任务后，由 Claude 更新此文件。新 session 开始时通过 `git pull` + 读取此文件来了解项目最新进展。

---

## 2026-07-14 — commit：Following 稳定性修复 + 业务日 + README

### 做了什么
- 合并本轮未提交改动并 push：Twitter 日期解析、Following select JSON 兼容、pipeline 进度 8/8、business_date 对齐、README 更新

---

## 2026-07-14 — Following select JSON 格式解析失败

### 做了什么
- 最新 pipeline run #3：`following.status=error`，`Following select response format invalid`（日期解析已修好，卡在 LLM 精选）
- `json_object` 模式常返回非数组包装；加固 `_coerce_results_list`，prompt 改为强制 `{"items":[...]}`
- 回归测试 + 真机 dry-run（`@levelsio` 5→kept 1）通过

### 遗留
- 需再跑一轮 refresh 才能写入 Following；未 commit

### 相关文件
- `backend/app/pipeline/following_select.py`, `backend/tests/test_following_select.py`

---

## 2026-07-14 — Pipeline 进度纳入 Following（8/8）

### 做了什么
- `total_steps` 从 7 → 8；RSS 结束后不再显示「完成」，改为进入第 8 步
- Following 旁路通过 `on_progress` 上报：抓取 `n/N`、精选、写入/跳过
- 结束后文案区分 RSS + Following 结果

### 相关文件
- `backend/app/pipeline/orchestrator.py`, `following_branch.py`, `tests/test_following_branch.py`

---

## 2026-07-14 — Following written:0 根因（Twitter 日期解析）

### 做了什么
- 排查 pipeline run #1：`following: {status: ok, written: 0}`，DB 无 following 条目
- 根因：`bird_client._parse_dt` 只用 `fromisoformat`，bird 实际返回 Twitter 经典时间（`Mon Jul 13 13:42:15 +0000 2026`），全部 `ValueError` 后静默丢弃 → 软空跳过
- 修复：`_parse_dt` 回退 `strptime(%a %b %d %H:%M:%S %z %Y)`；新增回归测试 `test_fetch_user_tweets_parses_twitter_created_at`
- 真机验证：修复后 `@levelsio` in_window=5/filtered=5，`@steipete` 18/4

### 证据
- pipeline_runs id=1 result.following.written=0；仅 6 账号 bird fetch 失败警告，其余“成功但空”
- dry-run：修复前 10/10 OpenAI 推文 cur_parse=False；修复后窗口内有候选

### 遗留
- 部分账号 bird `user-tweets` 仍偶发 `fetch failed`（非本次根因）
- 纯 RT 账号经 `filter_tweets` 后仍可能为 0（产品行为）
- 未 commit；需 Cooper 决定是否再跑一次手动 refresh

### 相关文件
- `backend/app/pipeline/bird_client.py`, `backend/tests/test_bird_client.py`

---

## 2026-07-13 — X Following (bird) + favorites upsert

### 本次完成的工作
- favorites 安全：persist upsert 按稳定键，去掉 orchestrator Step0 全日硬删
- Following 旁路：bird_client / sync_x_following / tweet_filter / following_select / following_branch
- Admin API + UI Tab；categories.yaml 增加 following；Hero 排除 following
- Docker 安装 Node + bird@0.8.0

### 关键决策
- RSS upsert 按 (date, category) 作用域调用；稳定键 raw_article_id
- Following 稳定键 external_id in source_links；不入 raw_articles
- 旁路与主线互不影响：RSS fail→error；仅 Following fail→success
- auto-sync 仅 x_accounts 空表时触发

### 相关文件
- backend/app/pipeline/persist.py, bird_client.py, sync_x_following.py, tweet_filter.py, following_select.py, following_branch.py, orchestrator.py
- backend/app/models.py (XAccount), admin.py, Dockerfile, categories.yaml
- frontend: HomeContent, XFollowingManager, admin page, api/types

### 遗留问题
- Cookie 续期需人工（AUTH_TOKEN/CT0）
- 真机 bird 拉 following/tweets 尚未在生产验证
- docker build 未在本机冒烟
- test_api 部分 favorites 401 为预存问题（若仍在）

---

## 2026-05-12 — 跨会话协作机制建立与 Git 工作流讨论

### 本次完成的工作
1. **建立跨设备协作机制**
   - 创建 `SESSION_LOG.md` 作为跨会话上下文桥梁
   - 更新 `CLAUDE.md` 新增 `Multi-Session Workflow` 段落，规范 session 开始/结束流程
   - 规则：重要任务完成后主动提醒用户 `git push`

2. **输出跨设备管理文档**
   - 在 `~/.claude/AI的使用技巧/` 仓库创建 `MULTI_DEVICE_SESSION_MANAGEMENT.md`
   - 已推送到 GitHub: `OPENW1NDOW/Summary-of-AI-experience`

3. **Git 工作流讨论**
   - 确认当前项目所有 commit 直接在 main 上，无分支
   - 讨论了个人开发者是否需要分支：小改动直接 main，大功能/重构用分支
   - 推荐简化工作流：`feat/xxx` 分支开发 → 合并回 main → 删除分支

### 关键决策
- 用 Git 托管的 `SESSION_LOG.md` 替代本地 session 文件作为跨设备上下文桥梁
- memory 文件保留给用户偏好/反馈，工作记录/决策放 SESSION_LOG.md

### 相关文件
- `CLAUDE.md` — 新增 Multi-Session Workflow 段落
- `SESSION_LOG.md` — 新建
- `~/.claude/AI的使用技巧/MULTI_DEVICE_SESSION_MANAGEMENT.md` — 完整文档

### 遗留问题
- Git 分支规范尚未写入 CLAUDE.md（用户未要求）
- 当前项目 main 分支是否为干净可运行状态未验证

---

## 2026-05-12 — 前端编译卡死修复

### 问题
前端 `npm run dev` 每次编译时系统卡死，甚至导致电脑死机。

### 根因
`next/font/google` 加载 5 个字体，其中 Noto Sans SC 和 Noto Serif SC 两个中文字体被 Google Fonts 拆成 200+ 个子集文件。Turbopack 每次冷编译要处理全部 221 个字体文件（550MB 缓存），加上 15.5GB 内存同时跑 Cursor + Claude Code + Python 后端，内存耗尽导致系统卡死。

### 修复方案
将中文字体从 `next/font/google` 改为 CSS `@import` 从 Google Fonts CDN 加载。浏览器直接处理字体，Turbopack 完全不参与。

### 效果
| 指标 | 修复前 | 修复后 |
|---|---|---|
| .next/ 缓存 | 550MB | 122MB (-77%) |
| 字体文件数 | 221 个 | 14 个 (-93%) |
| 编译就绪时间 | 卡死 | 931ms |

### 相关文件
- `frontend/app/globals.css` — 新增 CSS @import 加载中文字体
- `frontend/app/layout.tsx` — 移除 CJK 字体的 next/font/google 导入
- `frontend/package.json` — shadcn 从 dependencies 移到 devDependencies

### 遗留问题
- 中文字体目前走 Google CDN，国内访问可能较慢；如需完全自托管可后续优化
- Git 分支规范尚未写入 CLAUDE.md（用户未要求）

---

<!-- 模板，复制使用
## YYYY-MM-DD — 简短标题
- **做了什么**: ...
- **为什么**: ...
- **关键决策**: ...
- **相关文件**: ...
- **遗留问题**: ...
-->

---

## 2026-05-23 — 管理后台功能开发

### 做了什么
完整的管理后台系统，包含角色鉴权和 7 个管理模块。

**后端（8 个文件修改）：**
- `User` 模型新增 `is_admin` 字段，`init_db()` 安全 ALTER TABLE 迁移
- 新增 `PipelineRun` 模型记录流水线运行历史
- `require_admin` 鉴权中间件，`/api/auth/me` 返回 `is_admin`
- `admin.py` 完整重写：17 个带鉴权端点（仪表盘、流水线触发/状态/历史、数据源 CRUD/测试、新闻浏览/编辑/删除、用户角色管理、板块编辑、系统设置）
- 保留旧 `/api/admin/refresh` 和 `/api/admin/status` 无鉴权端点兼容首页

**前端（9 个新文件 + 4 个修改）：**
- `/admin` 页面：侧边栏 + 7 个 tab 组件
- 仪表盘：统计卡片、分类分布柱状图、最近流水线、系统信息
- 流水线：手动触发、实时进度条（3s 轮询）、运行历史表
- 数据源：列表、启用/代理开关、测试连通性、编辑名称/URL + 同步回 YAML
- 新闻管理：日期/板块筛选、分页、编辑弹窗、删除确认
- 用户管理：列表、管理员切换、防自我降权
- 板块管理：内联编辑名称和描述 + 同步回 YAML
- 系统设置：LLM 配置（脱敏 API Key）、代理地址、健康检查
- 首页和收藏页 header 新增管理员入口链接

### 为什么
网站缺少管理界面，之前只能手动编辑 YAML 文件和重启服务来管理数据源/分类。

### 关键决策
- 单页 sidebar tabs 而非子路由，匹配现有项目模式
- `is_admin` 迁移用安全 ALTER TABLE + 首个用户自动提权，无需手动操作
- 保留旧 admin 端点不加鉴权，避免破坏首页自动触发逻辑
- 测试 conftest 新增 `_bootstrap_admin` monkeypatch

### 相关文件
- `backend/app/models.py` — is_admin + PipelineRun
- `backend/app/api/admin.py` — 17 个管理端点
- `backend/app/api/deps.py` — require_admin
- `frontend/app/admin/page.tsx` — 管理后台主页
- `frontend/components/admin/*.tsx` — 7 个 tab 组件
- `frontend/lib/types.ts`, `frontend/lib/api.ts` — 类型和 API 客户端

### 遗留问题
- 收藏相关测试（8 个）缺少 auth headers，是预先存在的问题，非本次引入
- 系统设置写入 `.env` 后需重启服务才生效，无热更新
- `news-website.tar.gz` 和 `setup_proxy.sh` 未提交（不属于功能代码）

---

## 2026-06-01 — 修复摘要 429 限流导致板块缺失

### 本次完成的工作
1. **诊断问题**：分析 05-30 ~ 06-01 三天 pipeline 日志，发现 finance/business/international/social 等板块连续写入 0 条
2. **定位根因**：DeepSeek API 在并发摘要阶段频繁返回 429 Too Many Requests，后半部分板块的摘要全部失败
3. **修复**：
   - `summarizer.py`：429 时指数退避重试（最多 3 次，间隔 2s → 4s）
   - `orchestrator.py`：摘要并发从 5 降到 3

### 为什么
之前出现过 LLM 输出 list 类型 JSON 导致流水线崩溃的问题，这次是不同原因——API 限流。并发 5 个请求同时打 DeepSeek，越到后面的板块积累的 429 越多，最终全部失败。

### 关键决策
- 选择指数退避重试而非简单降并发，因为限流是暂时性的，重试可以恢复
- 并发从 5 降到 3 作为额外防护，减少触发限流的概率

### 相关文件
- `backend/app/pipeline/summarizer.py` — 加 429 重试逻辑
- `backend/app/pipeline/orchestrator.py` — 并发 5 → 3
