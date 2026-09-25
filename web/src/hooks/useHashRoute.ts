import { useCallback, useSyncExternalStore } from 'react';

/**
 * 用 hash 路由（#/game/<id>）：纯静态托管不需要任何 fallback 配置就能刷新、分享链接。
 */
function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

export function parseGameId(hash: string): string | null {
  const m = hash.match(/^#\/game\/([\w-]+)/);
  return m?.[1] ?? null;
}

export function useHashGameId(): [string | null, (id: string | null, opts?: { replace?: boolean }) => void] {
  const hash = useSyncExternalStore(
    subscribe,
    () => window.location.hash,
    () => '',
  );
  const navigate = useCallback((id: string | null, opts?: { replace?: boolean }) => {
    const next = id ? `#/game/${id}` : '#/';
    if (opts?.replace) {
      window.history.replaceState(null, '', next);
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    } else {
      window.location.hash = next;
    }
  }, []);
  return [parseGameId(hash), navigate];
}
