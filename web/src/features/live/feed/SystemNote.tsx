import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';

export type SystemTone = 'default' | 'god' | 'explode';

const TONES: Record<SystemTone, string> = {
  default: '',
  god: 'border border-dashed border-line bg-transparent text-left text-13 text-dim whitespace-pre-wrap',
  explode: 'border border-gold-line bg-gold-bg font-medium text-gold-hi',
};

export function SystemNote({ tone = 'default', children }: { tone?: SystemTone; children: ReactNode }) {
  return (
    <div
      className={cn(
        'rounded-[10px] bg-sys px-3.5 py-2.5 text-center wrap-anywhere max-phone:px-3 max-phone:text-13',
        TONES[tone],
      )}
    >
      {children}
    </div>
  );
}
