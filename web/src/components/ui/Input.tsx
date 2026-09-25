import type { InputHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export function Input({ className, type = 'text', ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input type={type} className={cn('form-control', className)} {...rest} />;
}
