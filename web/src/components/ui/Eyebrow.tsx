import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

/** 章节小标题：Cinzel 大写字距 */
export function Eyebrow({ className, ...rest }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        'font-latin text-12 tracking-[4px] text-gold uppercase max-phone:text-11 max-phone:tracking-[3px]',
        className,
      )}
      {...rest}
    />
  );
}
