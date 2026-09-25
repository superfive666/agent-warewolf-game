# 前端镜像：Node 构建 → nginx 静态托管（非 root，监听 8080）
#
#   docker build -t werewolf-web:latest web/
#   docker run --rm -p 8080:8080 --add-host=host.docker.internal:host-gateway \
#       -e API_UPSTREAM=http://host.docker.internal:8000 werewolf-web:latest
#
# /api/* 由 nginx 反代到 API_UPSTREAM（编排端 werewolf-server），浏览器看到的永远是同源。

# ───────── 1. 构建 ─────────
FROM node:22-alpine AS build
WORKDIR /app

# 先只拷依赖清单，npm ci 这一层能被缓存住
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# 构建期可选：前端和 API 不同源时，把 API 地址烧进产物
ARG VITE_API_BASE=
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

# ───────── 2. 运行 ─────────
FROM nginxinc/nginx-unprivileged:1.29-alpine

# 编排端地址。k8s 里要写全限定域名（nginx 的 resolver 不走 search 域）
ENV API_UPSTREAM=http://orchestrator:8000 \
    # 启动时从 /etc/resolv.conf 取 DNS，注入模板里的 ${NGINX_LOCAL_RESOLVERS}
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
