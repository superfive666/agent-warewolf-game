---
name: state-and-data
description: 处理数据请求、轮询、组件状态、hook 时使用 —— api 层怎么加端点、类型怎么写、轮询 / 取消 / 竞态怎么处理、什么时候用 useReducer、怎么避免在 effect 里 setState。改 src/api、src/hooks、features/*/use*.ts 或任何 useEffect 时先读。
---

# 状态与数据

## 请求只走 api 层

- `src/api/client.ts` 是唯一调用 `fetch` 的地方：拼 `VITE_API_BASE`、解析 JSON、把非 2xx 变成 `ApiError(status, message)`。
- `src/api/games.ts` 列出所有端点，组件和 hook 只调用 `api.xxx()`。
- `src/api/types.ts` 描述后端返回的结构。**只声明前端真正读到的字段**，可选字段用 `?:`。
  后端字段改名时先改这里，让 TypeScript 把所有使用点报出来。
- 后端负责中文化（`*_cn` 字段），前端直接展示，不要自己翻译枚举（`tests/test_i18n.py` 会检查）。

## effect 规则

1. 每个发请求的 effect 都要创建 `AbortController`，在 cleanup 里 `abort()`；catch 里先判断 `signal.aborted` 再处理错误。
2. 轮询用「递归 setTimeout」而不是 `setInterval`：上一次请求回来才排下一次，不会叠请求。参考 `features/game/useGameSession.ts`。
3. effect 里需要调用「最新的回调」但又不想把它放进依赖时，用 React 19 的 `useEffectEvent`。
4. **不要在 effect 里同步 setState 来「重置」状态**（eslint `react-hooks/set-state-in-effect` 会报）。替代做法：
   - 把数据和它的「来源键」存在一起（`{ gameId, god, events }`），渲染时发现键不匹配就当它不存在 —— 见 `sessionReducer.ts` + `selectSession`。
   - 或者给组件加 `key`，让 React 直接重建。
   - 或者在渲染期间根据 props 调整 state（`App.tsx` 里的 `attachedId`）。

## 选哪种状态

| 场景 | 用什么 |
|---|---|
| 单个开关、输入框 | `useState` |
| 多个字段互相牵连（改人数要同步座位数组） | `useReducer` + 纯函数 reducer（`useSetupForm.ts`），reducer 单测 |
| 服务端数据 + 轮询 | 自定义 hook 封装（`useGameSession`），组件只拿结果 |
| 跨很多层的全局能力（toast） | Context，拆成 `XxxContext.ts` / `XxxProvider.tsx` / `useXxx.ts` 三个文件 |
| 能从别的 state 算出来的 | **不存**，渲染时直接算 |

## 路由

用 hash 路由（`#/game/<id>`，见 `hooks/useHashRoute.ts`）：静态托管不需要任何回退配置，刷新和分享链接都能用。
不要引入需要服务端 fallback 的 history 路由。

## 下载

生成文件用 `lib/download.ts` 的 `downloadText()`（点击时临时建 blob URL，用完立即回收），
不要在 state 里长期持有 `blob:` URL。
