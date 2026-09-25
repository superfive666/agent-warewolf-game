---
name: frontend-verify
description: 前端改动完成、准备提交 / 推送之前使用 —— 依次跑类型检查、lint、格式、单测、构建，以及涉及样式时的真机截图核对。任何 web/ 下的改动在说「做完了」之前都要走一遍。
---

# 提交前检查

在 `web/` 目录下：

```bash
npm run check    # = typecheck + lint + format:check + test
npm run build    # tsc -b && vite build，产物在 dist/
```

四项全绿、构建成功才算完成。格式问题直接 `npm run format`，lint 能自动修的 `npm run lint:fix`。

## 改了和后端的交互

回到仓库根目录跑 Python 测试（有前端契约检查）：

```bash
python3 -m unittest discover -s tests -t .
```

## 改了样式 / 布局

设计已定稿，样式改动的目标通常是「和原来一模一样」或「只改了想改的地方」。
单测看不出视觉回归，要真的打开页面看：

1. `npm run build`，然后在仓库根目录 `python3 run_server.py`（会托管 `web/dist`），或者 `npm run dev`。
2. 用 Playwright 在 **1440×900（桌面）** 和 **390×844（手机）** 两个尺寸下截图：配置页 → 点「天黑请闭眼」→ 对局页（开关上帝视角）→ 复盘页各标签 → 历史对局弹窗。
   固定随机种子（配置页「随机种子」填同一个数），两次截图才能逐像素对比。
3. 对比改动前后的截图（改动前可以用 `git worktree add` 起一份旧版本跑在另一个端口）。

注意：环境里 Chromium 在 `/opt/pw-browsers`，不要 `playwright install`；项目自带的 playwright 版本不匹配时用
`chromium.launch({ executablePath: '/opt/pw-browsers/chromium-<ver>/chrome-linux/chrome' })`。

## 改了 Dockerfile / nginx

```bash
docker build -t werewolf-web:latest web/
docker run --rm -p 8080:8080 --add-host=host.docker.internal:host-gateway \
  -e API_UPSTREAM=http://host.docker.internal:8000 werewolf-web:latest
curl -I localhost:8080/                 # 200，Cache-Control: no-cache
curl -I localhost:8080/assets/<hash>.js # 200，长缓存
curl    localhost:8080/api/options      # 反代到编排端
curl    localhost:8080/healthz          # ok
```
