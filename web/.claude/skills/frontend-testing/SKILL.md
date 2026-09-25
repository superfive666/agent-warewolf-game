---
name: frontend-testing
description: 给前端写或改测试时使用 —— Vitest + Testing Library 的约定、测试放哪、测什么、怎么 mock fetch、fixtures 在哪。新增 model / reducer / 组件，或修一个前端 bug 时都应该先读，并补上对应测试。
---

# 前端测试

工具：Vitest（jsdom）+ @testing-library/react + @testing-library/user-event + jest-dom matchers。

```bash
npm test            # 跑一遍
npm run test:watch  # 开发时
```

## 放哪

- 测试和被测代码放一起：`xxx/__tests__/Xxx.test.ts(x)`。
- 共享测试数据在 `src/test/fixtures.ts`（`OPTIONS`、`snapshot()`）。需要新形态就往里加工厂函数，不要在每个测试里手抄大 JSON。
- 全局 setup 在 `src/test/setup.ts`（jest-dom、自动 cleanup）。

## 测什么（优先级从高到低）

1. **纯逻辑**：`model.ts`、`lib/*.ts`、reducer。输入 → 输出，最便宜也最稳。修 bug 先在这里写一个会失败的用例。
2. **关键交互**：用户能感知的行为 —— 切板子后座位数变了、缺密钥时出现警告、开局成功回调 id、失败时提示服务端错误。
3. **安全约束**：agent 输出的文本必须按纯文本渲染（见 `FeedItem.test.tsx` 的 `<img onerror>` 用例）。

不测：Tailwind class 名、纯展示的静态文案、第三方库本身。

## 写法

- 查元素优先用可访问性查询：`getByRole('button', { name: '套用到全部座位' })` > `getByText` > `getByTestId`。
  如果某个元素用 role 查不到，通常说明它的 ARIA 有问题 —— 先修组件。
- 交互用 `userEvent`，不要用 `fireEvent`。
- mock 网络用 `vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })))`，
  并在 `afterEach(() => vi.unstubAllGlobals())` 里还原。
- 需要 toast 的组件要包在 `<ToastProvider>` 里渲染。
- 异步出现的内容用 `findBy*`，不要 `waitFor(() => getBy*)` 套娃。

## 后端契约

`tests/test_i18n.py::test_frontend_uses_the_chinese_fields` 会扫描 `web/src/**/*.ts(x)`（不含 `__tests__`），
确认前端读的是后端给的 `*_cn` 字段。删掉或改名这些字段的使用会让 Python 测试失败。
