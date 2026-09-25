import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

import { Icon } from './Icon';

export type ChipTone = 'default' | 'wolves' | 'private';

interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  tone?: ChipTone;
  /** 禁用时显示小锁 */
  lockable?: boolean;
}

const TONES: Record<ChipTone, string> = {
  default: 'border-line text-vil-fg',
  wolves: 'border-wolf-line text-wolf-fg',
  private: 'border-priv-chip text-priv-fg',
};

export function Chip({ active, tone = 'default', lockable, className, children, ...rest }: ChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        'group inline-flex h-[34px] items-center gap-1 rounded-full border bg-transparent px-3.5 text-13 whitespace-nowrap',
        'max-phone:h-9',
        TONES[tone],
        active && 'border-gold bg-gold font-medium text-on-gold',
        'disabled:cursor-not-allowed disabled:border-dashed disabled:border-line-strong disabled:text-faint',
        className,
      )}
      {...rest}
    >
      {lockable && <Icon name="lock" className="hidden size-[13px] group-disabled:inline" />}
      {children}
    </button>
  );
}
