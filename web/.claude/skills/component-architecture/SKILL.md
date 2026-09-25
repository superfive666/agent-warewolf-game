---
name: component-architecture
description: 新增或拆分 React 组件时使用 —— 决定组件放哪一层（views / feature components / ui primitives）、怎么命名、何时拆分、props 怎么设计。凡是在 web/src 下新建 .tsx、把一个组件拆成多个、或者移动组件位置，都先读这个。
---

# 组件分层与拆分

## 目录分层（从大到小）

```
src/
├── App.tsx                  顶层：路由（hash）、当前步骤、把数据分发给视图。不写业务 UI
├── features/<feature>/      按业务拆：setup / live / review / history / game
│   ├── <Feature>View.tsx    这一步的页面骨架，只做布局 + 组合
│   ├── components/ 或子目录  只属于这个 feature 的组件（table/、feed/ …）
│   ├── model.ts             纯函数：规范化、拼请求、文案（不 import React）
│   ├── use<Xxx>.ts          这个 feature 的 hook / reducer
│   └── __tests__/
├── components/
│   ├── ui/                  无业务含义的原语：Button、Card、Select、Switch、Icon …
│   ├── layout/              全局框架：TopBar、StepNav、Brand
│   └── toast/               跨 feature 的 context
├── hooks/                   与业务无关的通用 hook（useMediaQuery、useHashGameId）
├── api/                     client.ts（唯一的 fetch 出口）、games.ts（端点）、types.ts（后端数据结构）
└── lib/                     纯工具：cn、format、game（领域规则）、download
```

依赖方向只能**向下**：`App → features → components/ui → lib`。
- `components/ui` 不能 import `features/*`，也不能知道「座位」「狼人」这些业务概念。
- feature 之间不互相 import；共享的东西下沉到 `lib/` 或 `components/ui/`。
- `api/` 只被 hook 和 feature 顶层组件调用，叶子组件只收 props。

## 什么时候拆

满足任一条就拆出去：
1. 文件超过 ~150 行，或 JSX 嵌套超过 4 层。
2. 一段 JSX 有自己的名字（「座位卡」「发言气泡」「桌心」）—— 有名字就该是组件。
3. 一段逻辑可以不依赖 React 表达（排序、文案、合法性）—— 挪进 `model.ts` / `lib/`，并写单测。
4. 同样的 className 串出现两次以上 —— 提成 `components/ui` 原语，或者组件内的常量。

不要为了拆而拆：只在一个地方用、10 行以内、没有独立名字的片段留在原处。

## 约定

- 一个文件一个导出组件，文件名 = 组件名（PascalCase.tsx）；hook 用 `useXxx.ts`；纯逻辑用 camelCase.ts。
- 用具名导出（`export function SeatCard`），不用 default export —— 重命名和搜索都更稳。
- Props 用 `interface XxxProps`，放在组件正上方。回调命名 `onXxx`，布尔用 `open/disabled/active` 这类形容词。
- 叶子组件优先收**原始值**（`seat`、`side`、`label`）而不是整个大对象，方便 `memo` 和测试。
- 「隐藏但不卸载」只在需要保留表单状态时用（SetupView 就是这样）；其余视图按条件渲染。
- 文本一律走 JSX 文本节点。**禁止 `dangerouslySetInnerHTML`**（ESLint 已拦）：所有文字都来自 agent 输出。

## 新增一个 feature 的步骤

1. 在 `api/types.ts` 补后端返回的字段（只写前端真正读到的）。
2. 在 `api/games.ts` 加端点。
3. 纯逻辑写进 `features/<x>/model.ts` + `__tests__/model.test.ts`。
4. 从 `<X>View.tsx` 骨架开始，自上而下拆组件；原语从 `components/ui` 拿，缺了再补。
5. 跑 `frontend-verify` skill 里的检查。
