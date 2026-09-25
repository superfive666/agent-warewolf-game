import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';

/** 金边圆章：座位号 / 历史对局人数 */
export function Medal({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'flex size-[34px] flex-none items-center justify-center rounded-full border border-medal',
        'font-serif text-15 font-bold text-gold-hi max-phone:size-8 max-phone:text-13',
        className,
      )}
    >
      {children}
    </span>
  );
}
