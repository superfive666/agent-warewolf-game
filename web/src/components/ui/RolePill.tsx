import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';
import type { RoleTone } from '@/lib/game';

const TONES: Record<RoleTone, string> = {
  wolf: 'border-wolf-line bg-wolf-bg text-wolf-fg',
  god: 'border-good-line bg-good-bg text-good-fg',
  vil: 'border-vil-line bg-vil-bg text-vil-fg',
};

interface RolePillProps {
  tone: RoleTone;
  className?: string;
  children: ReactNode;
}

export function RolePill({ tone, className, children }: RolePillProps) {
  return (
    <span
      className={cn(
        'rounded-full border px-3 py-1 text-13 max-phone:px-2.5 max-phone:py-[3px] max-phone:text-12',
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
