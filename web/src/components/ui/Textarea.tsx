import type { TextareaHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea className={cn('form-control h-auto resize-y py-2.5 leading-[1.6]', className)} {...rest} />
  );
}
