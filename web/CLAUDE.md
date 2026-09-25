# web/ —— 前端

Vite + React 19 + TypeScript（strict）+ Tailwind CSS v4。后端是仓库根目录的 Python 编排端，只提供 `/api/*`。

## 硬性约定

- **视觉设计已定稿**（`src/styles/index.css` 的 `@theme`）。改样式是「使用 token」，不是重新设计；组件里不写十六进制颜色。
- 组件从大到小分层：`App → features/<x>/<X>View → features/<x>/components → components/ui`，依赖只能向下。一个文件一个组件。
- 所有 HTTP 请求走 `src/api/`；后端字段改名先改 `src/api/types.ts`。
- 后端给的 `*_cn` 中文字段直接展示，不要在前端翻译枚举（`tests/test_i18n.py` 会检查）。所有面向人的文本都用中文。
- 禁止 `dangerouslySetInnerHTML`：文本全部来自 agent 输出。
- 用 hash 路由（`#/game/<id>`），产物用相对路径（`base: './'`），保证能当纯静态文件部署。

## 相关 skill（`.claude/skills/`）

| 什么时候                         | 读哪个                   |
| -------------------------------- | ------------------------ |
| 新建 / 拆分 / 移动组件           | `component-architecture` |
| 写 className                     | `tailwind-conventions`   |
| 请求、轮询、hook、useEffect      | `state-and-data`         |
| 写测试、修 bug                   | `frontend-testing`       |
| 交互组件、长列表                 | `a11y-and-performance`   |
| 说「做完了」之前                 | `frontend-verify`        |
| 构建 / Docker / nginx / 部署清单 | `frontend-deploy`        |

## 常用命令

```bash
npm run dev      # :5173，/api 代理到 :8000
npm run check    # typecheck + lint + format:check + test
npm run build    # → dist/
```
