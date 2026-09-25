import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';

import { Icon } from './Icon';

interface DisclosureProps {
  summary: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}

/** 轻量的「展开更多」：顶部一条分隔线 + 小箭头 */
export function Disclosure({ summary, className, bodyClassName, children }: DisclosureProps) {
  return (
    <details className={cn('group border-t border-rule pt-3', className)}>
      <summary className="no-marker flex min-h-8 cursor-pointer items-center gap-1.5 text-14 text-dim">
        <Icon name="chev" className="size-4 transition-transform group-open:rotate-180" />
        {summary}
      </summary>
      <div className={cn('pt-3', bodyClassName)}>{children}</div>
    </details>
  );
}
