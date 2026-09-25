import type { InputHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size' | 'onChange'> {
  size?: 'md' | 'sm';
  onChange?: (checked: boolean) => void;
}

/** 开关：本质是 checkbox，所以键盘 / 读屏行为都是原生的 */
export function Switch({ size = 'md', className, onChange, ...rest }: SwitchProps) {
  return (
    <input
      type="checkbox"
      role="switch"
      onChange={(e) => onChange?.(e.target.checked)}
      className={cn(
        'relative m-0 flex-none cursor-pointer appearance-none rounded-full bg-switch transition-colors',
        'after:absolute after:top-[3px] after:left-[3px] after:rounded-full after:bg-dim after:transition-[transform,background]',
        "after:content-['']",
        'checked:bg-gold checked:after:bg-on-gold',
        size === 'md'
          ? 'h-7 w-12 after:size-[22px] checked:after:translate-x-5'
          : 'h-[26px] w-11 after:size-5 checked:after:translate-x-[18px]',
        className,
      )}
      {...rest}
    />
  );
}
