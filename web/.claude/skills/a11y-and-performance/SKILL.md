---
name: a11y-and-performance
description: 做交互组件（按钮组、开关、标签页、弹窗、列表）或处理长列表 / 高频刷新时使用 —— 本项目的无障碍与性能基线：原生元素优先、ARIA 模式、键盘操作、memo 与 key、轮询下的渲染开销。
---

# 无障碍与性能基线

## 无障碍

- **原生元素优先**：开关是 `<input type="checkbox" role="switch">`，弹窗是 `<dialog>`（`components/ui/Sheet.tsx`，自带焦点管理和 Esc），折叠是 `<details>/<summary>`。能用原生的就不要自己拼 div。
- 可点击的东西一定是 `<button type="button">` 或 `<a href>`，不要给 div 加 onClick。
- 单选组：容器 `role="radiogroup" aria-label`，每项 `role="radio" aria-checked`（`Segmented`、`BoardPicker`、`DeploymentPicker`）。
- 多个独立开关：`aria-pressed`（`EffortPicker`、`Chip`）。
- 标签页：完整 WAI-ARIA tabs —— `tablist / tab / tabpanel`、`aria-controls`、`aria-selected`、roving `tabIndex`、左右方向键 + Home/End（`ReviewTabs`）。
- 折叠按钮：`aria-expanded` + `aria-controls`（`SeatCard`）。
- 纯装饰的 SVG / 元素加 `aria-hidden="true"`（`Icon` 默认就有）；只有图标的按钮必须有 `aria-label`。
- 表单控件都要有可见 label 或 `aria-label`；用 `Field` 组件时整块就是 `<label>`。
- 焦点样式由全局 `:focus-visible` 统一给，不要 `outline-none` 了事。
- 动画已在全局尊重 `prefers-reduced-motion`，新动画不需要再单独处理，但不要用 JS 驱动的动画绕开它。

## 性能

- 实况每 600ms 轮询一次，快照对象每次都是新的。长列表的行组件（`FeedItem`）用 `memo`，并且**只传原始值**
  （`side`、`agent`、`roleCn`），否则 memo 形同虚设。
- 列表 `key` 用稳定标识：座位用 `seat`，只追加的事件流用下标即可；会重排 / 删除的列表不能用下标。
- 自动滚到底用 `useLayoutEffect`（`useStickToBottom`），避免先闪一帧再跳。
- 大块内容（心路历程、会话存档）只渲染当前标签页，不要全部挂载再用 `hidden` 藏。
- 不要为了「可能有用」加 `useMemo / useCallback`；先确认真的有重复计算或破坏了 memo 再加。
- 新依赖要掂量体积：先看 `npm run build` 输出的 gzip 大小变化。
