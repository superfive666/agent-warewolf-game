# 狼人杀 Agent 沙箱 · 前端

Vite + React 19 + TypeScript（strict）+ Tailwind CSS v4。
后端是仓库根目录的 `werewolf-server`（Python，只提供 `/api/*`）。

## 开发

```bash
npm ci
npm run dev          # http://127.0.0.1:5173，/api 代理到 http://127.0.0.1:8000
```

另开一个终端在仓库根目录跑后端：`uv run werewolf-server`（或 `python3 run_server.py`）。

| 命令                              | 作用                                                   |
| --------------------------------- | ------------------------------------------------------ |
| `npm run dev`                     | 开发服务器（热更新）                                   |
| `npm run build`                   | 类型检查 + 生产构建 → `dist/`                          |
| `npm run preview`                 | 本地预览 `dist/`（同样代理 /api）                      |
| `npm run check`                   | typecheck + lint + format:check + test（提交前跑这个） |
| `npm test` / `npm run test:watch` | Vitest 单测 / 组件测试                                 |
| `npm run lint` / `npm run format` | ESLint / Prettier（含 Tailwind class 排序）            |

## 目录

```
src/
├── main.tsx / App.tsx      入口；App 只管路由（#/game/<id>）、当前步骤、数据分发
├── api/                    client（唯一 fetch 出口）/ games（端点）/ types（后端数据结构）
├── features/
│   ├── setup/              I  配置牌局：板子、座位阵容、规则、部署模式、开局
│   ├── live/               II 对局：状态栏、圆桌（table/）、实况流（feed/）
│   ├── review/             III 复盘：结果横幅、战报时间线、身份揭晓、心路历程、会话存档、原始数据
│   ├── history/            历史对局弹窗
│   └── game/               useGameSession：轮询事件 + 快照、结束后拉复盘
├── components/
│   ├── ui/                 原语：Button / Card / Select / Switch / Segmented / Chip / Sheet / Icon …
│   ├── layout/             TopBar / Brand / StepNav
│   └── toast/              全局提示
├── hooks/                  useHashGameId / useMediaQuery / useOptions
├── lib/                    cn / format / game（领域规则）/ download
└── styles/index.css        Tailwind 入口 + 设计 tokens（@theme）
```

开发规范在 [`.claude/skills/`](.claude/skills)：组件分层、Tailwind 用法、状态与数据、测试、无障碍与性能、提交前检查、部署。

## 部署

产物是纯静态文件（相对路径 + hash 路由），三种用法：

1. **编排端直接托管**：`npm run build` 后 `werewolf-server` 自动托管 `web/dist`。`deploy/docker/Dockerfile` 已内置这一步。
2. **纯静态 HTML**：把 `dist/` 放到任意静态托管 / CDN。API 在别的域名时，构建前设 `VITE_API_BASE`，编排端设 `WEREWOLF_CORS_ORIGINS`。
3. **nginx 镜像**：

   ```bash
   docker build -t werewolf-web:latest web/
   docker run -p 8080:8080 -e API_UPSTREAM=http://<编排端>:8000 werewolf-web:latest
   ```

   非 root、监听 8080；`/api/*` 反代到 `API_UPSTREAM`；`/assets/*` 长缓存、`index.html` 不缓存；`/healthz` 给探针。
   compose 见 `deploy/docker/compose.py`，k8s 见 `deploy/k8s/20-web.yaml`。

| 变量                    | 生效时机         | 说明                                                                |
| ----------------------- | ---------------- | ------------------------------------------------------------------- |
| `VITE_API_BASE`         | 构建期           | API 前缀，留空 = 同源。`docker build --build-arg VITE_API_BASE=...` |
| `WEREWOLF_API_PROXY`    | dev / preview    | `/api` 代理目标，默认 `http://127.0.0.1:8000`                       |
| `API_UPSTREAM`          | nginx 镜像运行期 | 反代目标；k8s 里写全限定域名                                        |
| `WEREWOLF_CORS_ORIGINS` | 编排端           | 允许跨域的来源（逗号分隔或 `*`），同源部署不用设                    |
| `WEREWOLF_WEB_DIR`      | 编排端           | 前端产物目录，默认 `web/dist`                                       |
