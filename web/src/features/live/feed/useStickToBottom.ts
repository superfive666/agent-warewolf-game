import { useCallback, useLayoutEffect, useRef, useState } from 'react';

const NEAR_PX = 80;

const nearBottom = (el: HTMLElement) => el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_PX;

/**
 * 聊天流式滚动：用户停在底部时，新内容进来自动滚到底；往上翻了就不打扰。
 * contentKey 变化 = 有新内容。
 */
export function useStickToBottom<T extends HTMLElement>(contentKey: unknown) {
  const ref = useRef<T>(null);
  const stick = useRef(true);
  const [atBottom, setAtBottom] = useState(true);

  const onScroll = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    stick.current = nearBottom(el);
    setAtBottom(stick.current);
  }, []);

  const scrollToBottom = useCallback(() => {
    const el = ref.current;
    stick.current = true;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  useLayoutEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [contentKey]);

  return { ref, onScroll, atBottom, scrollToBottom };
}
