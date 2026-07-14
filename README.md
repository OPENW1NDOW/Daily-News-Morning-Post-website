# 每日新闻早报网站

每天 8:00（Asia/Shanghai）自动从约 37 个 RSS 源拉取新闻，由 AI 完成筛选、分类、摘要、观点提取和背景补充；另有 **X Following 旁路**，经 [bird](https://github.com/steipete/bird) 抓取关注账号推文并精选。首页按板块呈现（RSS 每板块最多 6 条 + Following 最多 6 条）。支持多用户注册登录与独立收藏夹。

> **业务日**：与调度一致——上海时区 **08:00 前算前一天**。凌晨手动刷新写入的是「昨天」的早报日期；前后端 `today` / `today_count` 已按此对齐，避免 08:00 前空库连环触发。

---

## 在线访问

http://82.156.105.34

---

## 系统要求

| 依赖 | 版本 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+（Following / bird 需要；Docker 镜像已内置） |
| npm | 9+ |
| bird | `@steipete/bird`（全局或 `BIRD_BIN` 指向可执行文件） |
| 代理工具 | 需本地 HTTP 代理（海外 RSS + X API） |

> Windows / macOS / Linux 均可。

---

## 快速启动

### 1. 安装后端依赖

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 配置环境变量

在 `backend/` 目录下创建 `.env` 文件：

```env
LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
PROXY_URL=http://127.0.0.1:7897
DATABASE_URL=sqlite:///./data/news.db
RSSHUB_BASE_URL=http://localhost:1200
RSSHUB_AUTO_START=true

# X Following（可选；不配 Cookie 则旁路跳过）
X_AUTH_TOKEN=
X_CT0=
BIRD_BIN=bird
X_FOLLOWING_CANDIDATE_TOP_N=8
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | AI 大模型 API 密钥 | （必填） |
| `LLM_BASE_URL` | AI 大模型 API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名称 | `gpt-4o-mini` |
| `PROXY_URL` | HTTP 代理（海外 RSS + bird 访问 X） | `http://127.0.0.1:7890` |
| `DATABASE_URL` | SQLite 数据文件路径 | `sqlite:///./data/news.db` |
| `RSSHUB_BASE_URL` | RSSHub 实例地址 | `http://localhost:1200` |
| `RSSHUB_AUTO_START` | 流水线执行时自动启动 RSSHub | `true` |
| `X_AUTH_TOKEN` / `X_CT0` | x.com Cookie（Following） | 空则跳过 Following |
| `BIRD_BIN` | bird 可执行文件；Windows 常需 `bird.cmd` 绝对路径 | `bird` |
| `X_FOLLOWING_CANDIDATE_TOP_N` | LLM 精选后候选上限（最终入库最多 6） | `8` |

完整注释见 `backend/.env.example`。手动测 bird 时，Node 还需 `NODE_USE_ENV_PROXY=1` 与 `HTTPS_PROXY`（后端会从 `PROXY_URL` 注入）。

### 4. 启动

**终端 1 — 后端（端口 8000）：**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**终端 2 — 前端（端口 3000）：**

```bash
cd frontend
npm run dev
```

浏览器打开 `http://localhost:3000`。

> **跨设备访问：** 同一局域网下，手机/平板访问 `http://你电脑IP:3000` 即可使用。

---

## Docker 部署

```bash
# 构建并启动
docker-compose up -d --build

# 查看状态
docker ps

# 查看日志
docker logs news-backend -f
```

### 服务器部署

```bash
# 首次部署
git clone https://github.com/OPENW1NDOW/Daily-News-Morning-Post-website.git /opt/news-website
cd /opt/news-website
# 配置 .env 后启动
docker-compose up -d --build

# 后续更新
cd /opt/news-website
git pull origin main
docker-compose up -d --build
```

### 服务器代理配置

服务器需要代理访问海外 RSS 源。推荐使用 mihomo（Clash Meta）：

```bash
# 安装 mihomo
mkdir -p /etc/mihomo && cd /etc/mihomo
wget https://github.com/MetaCubeX/mihomo/releases/download/v1.19.0/mihomo-linux-amd64-v1.19.0.gz -O mihomo.gz
gunzip mihomo.gz && chmod +x mihomo

# 配置订阅（替换为你的订阅链接）
wget "你的订阅链接" -O config.yaml

# 启动
systemctl enable mihomo && systemctl start mihomo
```

`.env` 中配置：
```env
PROXY_URL=http://host.docker.internal:7897
```

`docker-compose.yml` 中需要添加：
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

---

## RSSHub 集成

部分平台（知乎、雪球、同花顺等）没有原生 RSS，通过 [RSSHub](https://github.com/DIYgod/RSSHub) 生成订阅源。

### 工作方式

- `RSSHUB_AUTO_START=true` 时，流水线执行前自动启动本地 RSSHub 实例
- 流水线完成后，RSSHub 保持运行直到后端退出
- 如果 RSSHub 已在运行，自动跳过启动

### RSSHub 源（5 个）

| 源 | 路由 | 板块 |
|---|---|---|
| 知乎热榜 | `/zhihu/hot` | 互联网 |
| 同花顺 | `/10jqka/realtimenews` | 金融投资 |
| 财新 | `/caixin/latest` | 商业与经济 |
| Hugging Face Papers | `/huggingface/daily-papers` | AI 论文 |
| Hacker News | `/hackernews/best` | 科技产业 |

### 自建 RSSHub（可选）

```bash
# 克隆
git clone --depth 1 https://github.com/DIYgod/RSSHub.git ../rsshub
cd ../rsshub && npm install

# 启动
npm run dev
```

生产环境建议用 Docker：

```bash
docker run -d --name rsshub -p 1200:1200 diygod/rsshub
```

然后将 `RSSHUB_BASE_URL` 改为 `http://rsshub:1200`（Docker 内部网络）。

---

## 流水线

### RSS 主线（7 步）+ Following 旁路

```
RSS: 抓取 → 日期过滤 → AI分类 → 选择Top-8 → 全文提取 → AI摘要 → 写入
Following（并行旁路，不阻塞 RSS 成功态）:
  sync 关注列表 → bird 拉推文 → 规则过滤 → LLM 精选打分 → upsert
```

进度轮询为 **8 步**：1–7 为 RSS，第 8 步为 Following（含「抓取 n/N」文案）。RSS 失败则整次 `error`；仅 Following 失败时主线仍可 `success`，结果里带 `following.status`。

`news_items` 按稳定键 **upsert**（收藏不因重跑被清空）；Following 无候选或硬失败时**不会 wipe** 当日已有 Following。

详见 [docs/workflow.md](docs/workflow.md)。

### 触发方式

- **自动**：每天 08:00（Asia/Shanghai）由 APScheduler 执行
- **手动**：首页自动触发 / Admin「立即抓取」，或 `POST /api/admin/refresh`

### 运行状态

```bash
GET /api/admin/status
```

返回 `today_count`（业务日）、`pipeline_running`、`progress`（`step` / `step_index` / `total_steps=8`）等。

## RSS 源配置

`backend/config/sources.yaml`，共 37 个源，按板块分组：

```yaml
- key: 36kr
  name: 36氪
  url: https://36kr.com/feed
  use_proxy: false    # 海外源设为 true
  enabled: true       # false 则跳过
```

- **`use_proxy`**：国内源不改，海外源设为 `true`
- **`enabled`**：可临时禁用失效源，不阻塞流水线
- RSSHub 源使用 `${RSSHUB_BASE_URL}` 占位符，运行时自动替换

---

## 板块

RSS 仍为 8 个内容板块；另有 **Following**（X 关注流精选），不参与首页 Hero 竞选。

| 板块 | 内容 |
|------|------|
| AI 与大模型 | 大语言模型、多模态、AI 产品、算法突破 |
| AI 前沿论文 | 学术论文、实验室突破、算法进展 |
| 科技产业 | 消费电子、硬件设备、软件应用 |
| 互联网 | 公司动态、平台运营、社交网络、电商 |
| 商业与经济 | 企业战略、商业模式、产业格局 |
| 金融投资 | 股市、投资机构、宏观经济、加密货币 |
| 国际时政 | 地缘政治、外交事件、战争冲突 |
| 社会人文 | 社会热点、民生问题、文化现象 |
| Following | 关注账号推文精选（独立评分，非 RSS classifier） |

Following 评分：规则去掉纯 RT / 过短文本后，由独立 LLM prompt 输出 `keep` + `score(0–100)` + 一句话摘要，按分排序入库（与 RSS `importance` 标尺不共用）。

Admin 中可管理启用账号与手动同步关注列表（需管理员登录）。

---

## API 概览

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/api/health` | 健康检查 | - |
| GET | `/api/categories` | 板块清单（含今日条数） | - |
| GET | `/api/news?date=YYYY-MM-DD&category=xxx` | 某日某板块新闻 | 可选 |
| GET | `/api/news/{id}` | 新闻详情 | 可选 |
| POST | `/api/auth/register` | 注册 `{"username", "password"}` | - |
| POST | `/api/auth/login` | 登录，返回 JWT token | - |
| GET | `/api/auth/me` | 获取当前用户信息 | 需要 |
| GET | `/api/favorites?page=1` | 收藏列表 | 需要 |
| POST | `/api/favorites` | 添加收藏 `{"news_item_id": 1}` | 需要 |
| DELETE | `/api/favorites/{news_item_id}` | 取消收藏 | 需要 |
| POST | `/api/admin/refresh` | 手动触发流水线 | - |
| GET | `/api/admin/status` | 流水线运行状态 / 进度 | - |
| GET | `/api/admin/x-following/accounts` | Following 账号列表 | 管理员 |
| PATCH | `/api/admin/x-following/accounts/{id}` | 启用/禁用账号 | 管理员 |
| POST | `/api/admin/x-following/sync` | 同步 X 关注列表 | 管理员 |
| GET | `/api/admin/x-following/status` | Following Cookie / 同步状态 | 管理员 |

> 需要认证的接口在 Header 中添加：`Authorization: Bearer <token>`

---

## 运行测试

```bash
cd backend
pip install pytest httpx
pytest tests/ -v
```

---

## 多用户系统

网站支持多用户注册登录，每个用户有独立的收藏夹。

### 功能

- 用户注册/登录（用户名 + 密码）
- JWT token 认证（7 天有效期）
- 收藏按用户隔离
- 未登录可浏览新闻，收藏需登录

### 数据库模型

```
User (id, username, password_hash, created_at)
Favorite (id, user_id, news_item_id, favorited_at)
```

---

## 常见问题

### 海外源全部拉取失败

1. 确认代理工具已开启
2. 检查 `.env` 中 `PROXY_URL` 端口与代理工具一致
3. 重启后端服务

### AI 大模型提示余额不足

每日成本约 ¥0.2-0.5。登录模型服务商控制台查看余额。

### uvicorn 启动报 `ModuleNotFoundError`

确认在 `backend/` 目录下启动，或设置 `PYTHONPATH=.`。

### SQLite 数据库损坏

删除 `backend/data/news.db` 后重启，表结构自动重建。

### 某板块不到 6 条

正常现象。当天对应领域新闻不足、或部分摘要调用失败时会出现。

### 08:00 前首页一直自动刷新

已修复：业务日与日历日不一致时，`today_count` 与首页日期应对齐到「08:00 前算昨天」。若仍循环，确认前后端已拉取含 `business_date` / `todayStr` 的版本。

### Following 为空或不更新

1. `.env` 是否配置了有效的 `X_AUTH_TOKEN` / `X_CT0`
2. `PROXY_URL` 可用；bird 能访问 x.com（Node 需代理环境变量）
3. Windows 上 `BIRD_BIN` 是否指向真实的 `bird.cmd`
4. Admin → X Following：账号是否启用；流水线结果里 `following.status` / `error`
5. 纯转发账号会被规则过滤；LLM 精选失败时不会 wipe 旧数据，也不会写入新数据

---

## 部署

生产部署清单见 [docs/deploy-todo.md](docs/deploy-todo.md)。

架构：

```
用户浏览器
    ↓ HTTPS
┌──────────────────────────────┐
│  Nginx (反代 + SSL)           │
│  ├─ /      → Next.js :3000   │
│  └─ /api   → FastAPI :8000   │
└──────────────────────────────┘
         │ docker 网络
    ┌────┴────┐
    │ FastAPI │ → SQLite (volume)
    │ + 调度器 │ → RSSHub (container)
    │         │ → LLM API
    └─────────┘
```
