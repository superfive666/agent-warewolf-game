import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import { ToastContext } from './ToastContext';

/** 全局只有一条提示：新的顶掉旧的 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const show = useCallback((msg: string, ms = 4000) => {
    setMessage(msg);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), ms);
  }, []);

  useEffect(() => () => clearTimeout(timer.current), []);

  return (
    <ToastContext value={show}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className={[
          'fixed bottom-8 left-1/2 z-50 max-w-[calc(100vw-32px)] -translate-x-1/2 rounded-xl border border-wolf-line bg-wolf-bg',
          'px-[18px] py-3 text-14 text-wolf-soft shadow-[0_10px_30px_rgba(0,0,0,.4)]',
          message ? '' : 'hidden',
        ].join(' ')}
      >
        {message}
      </div>
    </ToastContext>
  );
}
