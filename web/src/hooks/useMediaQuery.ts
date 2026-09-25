import { useSyncExternalStore } from 'react';

/** 订阅一个 CSS media query，例如 useMediaQuery('(max-width: 640px)') */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener('change', onChange);
      return () => mql.removeEventListener('change', onChange);
    },
    () => window.matchMedia(query).matches,
    () => false,
  );
}

export const PHONE_QUERY = '(max-width: 640px)';
