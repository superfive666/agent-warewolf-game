import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export function IconButton({ className, type = 'button', ...rest }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={cn(
        'flex h-11 min-w-11 items-center justify-center gap-2 rounded-[10px] border-none bg-transparent px-2',
        'text-14 text-dim hover:text-gold-hi',
        className,
      )}
      {...rest}
    />
  );
}
