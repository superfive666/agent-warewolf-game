---
name: tailwind-conventions
description: 写或改 className 时使用 —— Tailwind v4 在本项目里的用法约定：只用 design tokens、像素命名的字号、桌面优先的 max-* 断点、cn() 合并、什么时候写 @utility。视觉设计本身已定稿，这里只管「怎么用」。
---

# Tailwind 用法约定

视觉规范（城堡夜色：深蓝 + 烛金）**已经定稿**，全部定义在 `src/styles/index.css` 的 `@theme` 里。
写样式时是在「使用」这套 token，不是在做设计。

## 颜色：只用 token

```tsx
// ✅
<div className="border-line bg-card text-gold-hi" />
// ❌ 组件里出现十六进制
<div className="bg-[#15224A]" />
```

真的缺颜色时：先在 `@theme` 里加一个有语义的名字（`--color-xxx`），再在组件里用。
阴影、渐变里要引用颜色，写 `var(--color-gold-hi)`。

## 字号：按像素命名

`--text-*` 被重置成了像素刻度，`text-13` = 13px，`text-12_5` = 12.5px。**只设字号，不改行高**
（行高由 body 的 1.6 继承，需要时显式写 `leading-[1.7]`）。
没有 `text-sm / text-lg` 这些默认档 —— 用到新字号就去 `@theme` 加一档。

## 响应式：桌面优先

设计稿是桌面优先的，所以用 `max-*` 往下覆盖：

| variant       | 条件          |
|---------------|---------------|
| `max-laptop:` | ≤ 1180px      |
| `max-tablet:` | ≤ 960px       |
| `max-phone:`  | ≤ 640px       |

```tsx
<Card className="p-7 max-phone:p-4" />
```

页面左右留白用 `px-gutter`（64 → 32 → 16，随断点变化），不要各写各的。
JS 里需要判断断点时用 `useMediaQuery(PHONE_QUERY)`，不要读 `window.innerWidth`。

## 合并 className：用 `cn()`

```tsx
import { cn } from '@/lib/cn';
<button className={cn('h-11 rounded-xl', active && 'bg-gold text-on-gold', className)} />
```

`cn` = clsx + tailwind-merge（已教会它识别 `text-13` 是字号），后写的覆盖先写的。
组件对外暴露 `className` 时一律放在 `cn()` 最后。

## 状态样式优先用 ARIA / 伪类 variant

用 `aria-checked:`、`aria-pressed:`、`disabled:`、`group-open:` 驱动样式，
而不是再维护一个 `isOn` class —— 语义和样式天然同步。

## 什么时候写 `@utility`

只有下面几类写进 `index.css`：
- 需要伪元素 / 多层背景的复杂效果（`dead-cross`）。
- 所有表单控件共用的一组基础样式（`form-control`、`select-chevron`）。
- 浏览器兼容性补丁（`no-scrollbar`、`no-marker`）。

其余一律写在组件的 className 里。**不要**新建 `.xxx {}` 普通 class，也不要写 `@apply` 大段复刻旧 CSS。

## Tailwind preflight 的坑

- `h1/h2/h3` 的字重被重置成 inherit —— 标题要显式写 `font-bold / font-black`。
- `svg` 默认 `display:block; vertical-align:middle` —— 行内图标要写 `inline align-baseline`。
- `button` 没有 cursor:pointer —— `index.css` 已统一补上。
- v4 的 `rounded-full` 是「无限大圆角」，非正方形元素会变成跑道形；要椭圆（圆桌桌面）写 `rounded-[50%]`。

## 格式

`prettier-plugin-tailwindcss` 会自动排序 class，`npm run format` 即可，不要手动排。
