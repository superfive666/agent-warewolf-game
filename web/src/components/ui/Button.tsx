import type { ButtonHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export type ButtonVariant = 'default' | 'primary' | 'outline' | 'danger' | 'cta';

const VARIANTS: Record<ButtonVariant, string> = {
  default: '',
  primary: 'border-gold bg-gold font-bold text-on-gold hover:bg-gold-hi',
  outline: 'border-gold text-gold-hi hover:bg-gold-bg',
  danger: 'border-wolf-line text-wolf-fg hover:bg-wolf-bg',
  cta: [
    'h-16 gap-3 rounded-[14px] border-none bg-gold text-on-gold hover:bg-gold-hi',
    'shadow-[0_10px_30px_rgba(214,178,94,.25),inset_0_0_0_1px_var(--color-gold-hi)]',
    'max-phone:h-[54px]',
  ].join(' '),
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({ variant = 'default', className, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-line bg-transparent px-[18px]',
        'text-14 whitespace-nowrap text-fg no-underline disabled:cursor-not-allowed disabled:opacity-50',
        VARIANTS[variant],
        className,
      )}
      {...rest}
    />
  );
}
