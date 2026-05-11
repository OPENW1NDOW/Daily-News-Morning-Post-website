# 每日新闻早报网站

每天 8:00 自动从 37 个 RSS 源拉取新闻，由 AI 大模型完成筛选、分类、摘要、观点提取和背景补充，按 8 个板块每板块 6 条呈现。前端为简洁的卡片信息流。

---

## 系统要求

| 依赖 | 版本 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| 代理工具 | 需本地 HTTP 代理（海外源拉取用） |

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
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | AI 大模型 API 密钥 | （必填） |
| `LLM_BASE_URL` | AI 大模型 API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 模型名称 | `gpt-4o-mini` |
| `PROXY_URL` | HTTP 代理地址，海外源拉取用 | `http://127.0.0.1:7890` |
| `DATABASE_URL` | SQLite 数据文件路径 | `sqlite:///./data/news.db` |
| `RSSHUB_BASE_URL` | RSSHub 实例地址 | `http://localhost:1200` |
| `RSSHUB_AUTO_START` | 流水线执行时自动启动 RSSHub | `true` |

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

### 7 步流程

```
RSS抓取 → 日期过滤 → AI分类 → 选择Top-8 → 全文提取 → AI摘要 → 写入数据库
```

详见 [docs/workflow.md](docs/workflow.md)。

### 触发方式

- **自动**：每天 08:00（Asia/Shanghai）由 APScheduler 执行
- **手动**：首页点击"立即抓取"按钮，或 `POST /api/admin/refresh`

### 运行状态

```bash
GET /api/admin/status
```

---

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

## 8 个板块

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

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/categories` | 板块清单（含今日条数） |
| GET | `/api/news?date=YYYY-MM-DD&category=xxx` | 某日某板块新闻 |
| GET | `/api/news/{id}` | 新闻详情 |
| GET | `/api/favorites?page=1` | 收藏列表 |
| POST | `/api/favorites` | 添加收藏 `{"news_item_id": 1}` |
| DELETE | `/api/favorites/{news_item_id}` | 取消收藏 |
| POST | `/api/admin/refresh` | 手动触发流水线 |
| GET | `/api/admin/status` | 流水线运行状态 |

---

## 运行测试

```bash
cd backend
pip install pytest httpx
pytest tests/ -v
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
