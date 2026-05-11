# 生产部署 To Do 清单

> 目标：将项目部署到云服务器，正式上线运行

---

## P0 — 上线阻塞项（不做不能上线）

### 1. Docker 容器化
- [ ] 编写 `backend/Dockerfile`（Python 3.11 + uvicorn）
- [ ] 编写 `frontend/Dockerfile`（Node 18，`next build` standalone 模式）
- [ ] 编写 `docker-compose.yml`（fastapi + nextjs + nginx 三个服务）
- [ ] 配置 Docker volume 持久化 SQLite 数据和日志
- [ ] 验证 `docker-compose up` 一键启动全部服务

### 2. Nginx 反向代理
- [ ] 编写 `nginx/nginx.conf`
  - `/` → Next.js (port 3000)
  - `/api` → FastAPI (port 8000)
- [ ] 配置 HTTPS（Let's Encrypt 证书，certbot 自动续期）
- [ ] 配置 HTTP → HTTPS 强制跳转
- [ ] 配置安全响应头（X-Frame-Options, X-Content-Type-Options, CSP）

### 3. Admin 接口鉴权
- [ ] 新增环境变量 `ADMIN_TOKEN`（管理员密钥）
- [ ] `/api/admin/refresh` 和 `/api/admin/status` 添加 Token 校验（Header 或 Query 参数）
- [ ] 未授权请求返回 401

### 4. CORS 限制
- [ ] `allow_origins` 从 `["*"]` 改为只允许生产域名
- [ ] 通过环境变量 `ALLOWED_ORIGINS` 配置，支持多域名

### 5. 前端生产 API 路由
- [ ] 确认 nginx 反代模式下前端 `/api/*` 请求能正确转发到后端
- [ ] 移除或条件化 `next.config.ts` 中的 dev-only rewrites
- [ ] `frontend/.env.local` 配置 `NEXT_PUBLIC_API_URL`（nginx 反代模式下可留空）

---

## P1 — 上线前建议完成（影响稳定性）

### 6. 数据库
- [ ] 保留 SQLite 方案（单机够用），但配置每日自动备份
- [ ] 编写备份脚本：每天凌晨 `sqlite3 news.db ".backup backup.db"` + 压缩
- [ ] 备份文件保留最近 7 天，自动清理旧备份
- [ ] 备份存储到 volume 或挂载目录（后续可扩展到对象存储）

### 7. 密钥安全
- [ ] 确认 `backend/.env` 从未被 git 提交（检查 git history）
- [ ] 如果泄露过，轮换 LLM_API_KEY
- [ ] `docker-compose.yml` 中通过 `env_file` 加载 `.env`，不硬编码
- [ ] 添加 `.dockerignore` 排除 `.env`、`node_modules`、`__pycache__` 等

### 8. 后端健壮性
- [ ] 添加全局异常处理中间件（捕获未处理异常，返回统一 JSON 错误格式，不暴露堆栈）
- [ ] 添加请求日志中间件（记录 method、path、status、耗时）
- [ ] 日志级别通过环境变量 `LOG_LEVEL` 配置（默认 INFO）

### 9. Next.js 生产优化
- [ ] `next.config.ts` 添加 `output: "standalone"` 以支持 Docker 部署
- [ ] 确认 `npm run build` 无报错，页面正常渲染

### 10. 域名与 DNS
- [ ] 购买域名
- [ ] 配置 DNS A 记录指向服务器公网 IP
- [ ] 验证域名解析正确

---

## P2 — 上线后尽快补（1-2 周内）

### 11. 监控与告警
- [ ] 添加 `/api/health` 详细检查（数据库连接、调度器状态）
- [ ] 流水线执行失败时发送通知（可选：企业微信/飞书/邮件 webhook）
- [ ] 记录每日流水线执行结果（成功/失败、文章数量、耗时）

### 12. CI/CD
- [ ] 创建 `.github/workflows/deploy.yml`
- [ ] Push 到 main 分支时自动：运行测试 → 构建镜像 → 部署到服务器
- [ ] 配置 SSH 密钥或 deploy key 实现自动部署

### 13. 流水线重试机制
- [ ] 流水线失败后自动重试 1 次（间隔 10 分钟）
- [ ] 重试仍失败则记录错误日志，等待次日定时触发

---

## P3 — 后续优化（有空再做）

### 14. 测试补全
- [ ] 补充 fetcher、extractor、summarizer 模块的单元测试
- [ ] 补充前端基础测试（关键页面渲染、API 调用）
- [ ] 配置 pytest-cov 生成覆盖率报告

### 15. 数据库迁移
- [ ] 初始化 Alembic（`alembic init`）
- [ ] 为现有表结构生成初始迁移脚本
- [ ] 后续表结构变更通过 `alembic revision` 管理

### 16. 日志优化
- [ ] 日志格式改为 JSON（便于后续接入日志平台）
- [ ] 添加请求 correlation ID 便于追踪

### 17. RSSHub 自建实例
- [ ] docker-compose 中添加 RSSHub 服务
- [ ] 配置小红书/微博等平台的 Cookie
- [ ] sources.yaml 中添加 RSSHub 路由

### 18. 安全加固
- [ ] 添加速率限制（slowapi），防止 API 滥用
- [ ] 添加依赖漏洞扫描（pip-audit、npm audit）
- [ ] 收藏接口添加基础 CSRF 防护

---

## 部署架构

```
用户浏览器
    ↓ HTTPS (443)
┌──────────────────────────────┐
│  Nginx 容器 (反代 + SSL)      │
│  ├─ /      → Next.js :3000   │
│  └─ /api   → FastAPI :8000   │
└──────────────────────────────┘
         │ docker 网络
    ┌────┴────┐
    │ FastAPI │ → SQLite (volume 持久化)
    │ + 调度器 │ → 海外 RSS 源 (直连或代理)
    │         │ → LLM API (DeepSeek)
    └─────────┘
```

## 云服务器推荐

| 优先级 | 方案 | 价格 | 说明 |
|--------|------|------|------|
| 首选 | 阿里云/腾讯云 香港轻量 2核2G | ~40-60 元/月 | 国内访问快 + 海外 RSS 直连 |
| 备选 | 国内轻量 + 已有代理 | ~50-80 元/月 | 需确保代理稳定 |

## 费用预估

| 项目 | 费用 |
|------|------|
| 云服务器 | ~40-60 元/月 |
| 域名 | ~60 元/年 |
| SSL 证书 | 免费（Let's Encrypt） |
| LLM API | 几毛钱/天 |
| **月均总计** | **~50-70 元** |
