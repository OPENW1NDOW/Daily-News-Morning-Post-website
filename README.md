# 每日新闻早报网站

每天 8:00 自动从 ~40 个 RSS 源拉取新闻，由 AI 大模型完成筛选、分类、摘要、观点提取和背景补充，按 10 个板块每板块 6 条呈现。前端为简洁的卡片信息流。

---

## 系统要求

| 依赖 | 版本 |
|------|------|
| Python | 3.11+ |
| Node.js | 18+ |
| npm | 9+ |
| 代理工具（VPN） | 需本地 SOCKS5/HTTP 代理（海外源拉取用） |

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
PROXY_URL=http://127.0.0.1:7897
DATABASE_URL=sqlite:///./data/news.db
```

| 变量 | 说明 |
|------|------|
| `LLM_API_KEY` | AI 大模型 API 密钥（DeepSeek、OpenAI、小米 MiMo 等均可，需兼容 OpenAI 接口） |
| `LLM_BASE_URL` | AI 大模型 API 地址，根据你使用的模型服务商填写 |
| `PROXY_URL` | HTTP 代理地址，海外 RSS 源拉取用。端口改为你的代理工具实际端口 |
| `DATABASE_URL` | SQLite 数据文件路径，默认即可 |

### 4. 启动

**终端 1 — 后端（端口 8000）：**

```bash
cd backend
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux
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

## 配置说明

### RSS 源 (`backend/config/sources.yaml`)

每个源的字段：

```yaml
- key: 36kr
  name: 36氪
  url: https://36kr.com/feed
  use_proxy: false   # 海外源设为 true
  enabled: true       # false 则跳过该源
```

- **`use_proxy`**：国内源不改，海外源设为 `true` 后会通过 `PROXY_URL` 拉取
- **`enabled`**：可临时禁用失效的源，不会阻塞整体流水线

新增源：在对应板块注释下添加一条即可。源拉取失败时会自动标记 `last_status=failed`，不阻塞流水线。

### 板块 (`backend/config/categories.yaml`)

10 个固定板块，修改后需要同步更新 `backend/app/pipeline/classifier.py` 中的 `CATEGORIES` 列表和 `_CATEGORY_DESC`。

---

## 流水线触发

- **自动**：每天 8:00（Asia/Shanghai）由 APScheduler 自动执行
- **手动**：首次访问网页时，如果今日无数据会显示"立即抓取"按钮，点击触发
- **API**：POST `http://localhost:8000/api/admin/refresh`

查询状态：GET `http://localhost:8000/api/admin/status`

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
venv\Scripts\activate
pip install pytest httpx
pytest tests/ -v
```

---

## 常见问题

### 海外源全部拉取失败

1. 确认代理工具已开启（Clash / V2Ray / SSR 等）
2. 检查 `.env` 中 `PROXY_URL` 端口与代理工具一致（常见端口：7890、7897、10809）
3. 浏览器访问 `https://www.bbc.com` 确认代理生效
4. 重启后端服务

### AI 大模型提示余额不足

登录你使用的模型服务商控制台查看余额。每日成本约 ¥0.2-0.5（取决于每天拉取的新闻总量）。

### uvicorn 启动报 `ModuleNotFoundError`

确认在 `backend/` 目录下启动，且虚拟环境已激活。也可设置 PYTHONPATH：

```bash
# Windows
set PYTHONPATH=.
uvicorn app.main:app --reload

# macOS/Linux
PYTHONPATH=. uvicorn app.main:app --reload
```

### SQLite 数据库损坏

删除 `backend/data/news.db` 后重启服务。表结构会自动重建，历史数据会丢失，但下次流水线会重新拉取当日数据。

### 某板块不到 6 条

这是正常的。原因可能是：
- 当天对应领域的新闻总量不足
- 部分源的 AI 摘要调用失败（不阻塞整体，从备选中补充后仍可能不足 6 条）
- 查看 `backend/logs/pipeline.log` 确认具体原因

### 首页打开为空白

1. 确认后端已启动（`http://localhost:8000/api/health` 能返回 `{"ok":true}`）
2. 打开浏览器控制台（F12 → Console）查看是否有 CORS 或网络错误
3. 如果今日还未抓取，点击"立即抓取今日新闻"按钮

---

## 部署到云服务器（可选）

将项目迁移到云服务器后，可在任何设备通过公网访问：

1. 服务器安装 Python 3.11+ / Node 18+
2. 克隆项目，按"快速启动"步骤安装依赖和配置 `.env`
3. 后端建议使用 `--host 0.0.0.0` 监听所有网卡
4. 前端修改 `.env.local`：`NEXT_PUBLIC_API_URL=http://你的服务器IP:8000`
5. 生产环境建议用 nginx 反向代理 + HTTPS
6. 前端 `npm run build && npm run start`，或部署到 Vercel
7. 如服务器在国内，海外源可能不需要代理；视服务器网络环境调整 `use_proxy`
