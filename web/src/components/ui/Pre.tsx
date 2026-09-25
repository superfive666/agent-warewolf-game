import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

/** 等宽文本块（prompt、原始 JSON 等） */
export function Pre({ className, ...rest }: HTMLAttributes<HTMLPreElement>) {
  return (
    <pre
      className={cn(
        'max-h-[560px] overflow-auto rounded-[10px] border border-line bg-inset p-3.5',
        'font-mono text-12_5 leading-[1.55] break-words whitespace-pre-wrap',
        className,
      )}
      {...rest}
    />
  );
}
