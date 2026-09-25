---
name: frontend-deploy
description: 构建和部署前端时使用 —— 三种方式（编排端直接托管 / 纯静态 HTML / nginx 镜像）、相关环境变量（VITE_API_BASE、API_UPSTREAM、WEREWOLF_CORS_ORIGINS、WEREWOLF_WEB_DIR）、缓存策略。改 vite.config.ts、Dockerfile、nginx 配置或部署清单前先读。
---

# 前端部署

`npm run build` 的产物 `web/dist/` 是纯静态文件（`index.html` + 带内容 hash 的 `assets/*`），
资源用**相对路径**（`base: './'`），路由用 hash —— 所以放在任何静态托管、任何子路径下都能直接用。

## 三种部署方式

| 方式 | 怎么做 | 适合 |
|---|---|---|
| 编排端直接托管 | `npm run build` 后 `werewolf-server` 自动托管 `web/dist`（`deploy/docker/Dockerfile` 已内置这一步） | 单机、本地、一个镜像搞定 |
| 纯静态 HTML | 把 `dist/` 丢到 S3 / OSS / GitHub Pages / 任意 web 服务器 | 前端上 CDN，API 在别处 |
| nginx 镜像 | `docker build -t werewolf-web web/`，`/api/*` 由 nginx 反代给编排端 | k8s / compose 里前后端分开扩容、分开发版 |

## 环境变量

| 变量 | 在哪生效 | 作用 |
|---|---|---|
| `VITE_API_BASE` | **构建期**（`npm run build` / `docker build --build-arg`） | API 前缀。留空 = 同源。纯静态部署到别的域名时填编排端地址 |
| `WEREWOLF_API_PROXY` | `npm run dev` / `preview` | 开发时 `/api` 代理目标，默认 `http://127.0.0.1:8000` |
| `API_UPSTREAM` | nginx 镜像运行期 | 反代目标。k8s 里写 FQDN（`http://werewolf.werewolf.svc.cluster.local:80`），nginx resolver 不走 search 域 |
| `WEREWOLF_CORS_ORIGINS` | 编排端 | 前端和 API 不同源时放行的来源，逗号分隔或 `*`。同源部署不要设 |
| `WEREWOLF_WEB_DIR` | 编排端 | 前端产物目录，默认 `<repo>/web/dist` |

`VITE_*` 会被**烧进产物**，不要往里放任何密钥。

## nginx 镜像要点（`web/Dockerfile` + `web/nginx/default.conf.template`）

- 基于 `nginxinc/nginx-unprivileged`：非 root，监听 **8080**。
- 配置是模板，启动时用环境变量渲染；`NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1` 让 `resolver` 取容器自己的 DNS。
- `proxy_pass` 用变量 + `resolver`：API 暂时解析不到时 nginx 也能启动，静态页面照常可用（`/api` 返回 502）。
- 缓存：`/assets/*` 永久缓存，`index.html` 不缓存 —— 发版后刷新即生效。
- 没有 SPA 回退：hash 路由用不到，而且相对路径的产物被回退到深层路径时会加载错资源。未知路径直接 404。
- `/healthz` 给探针用。

## 清单

- compose：`python3 deploy/docker/compose.py` 生成的文件里带 `web` 服务（8080）。
- k8s：`deploy/k8s/20-web.yaml`（Deployment + Service，可多副本）。
