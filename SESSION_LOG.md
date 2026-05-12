# Session Log

每次 Claude Code session 完成重要任务后，由 Claude 更新此文件。新 session 开始时通过 `git pull` + 读取此文件来了解项目最新进展。

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
