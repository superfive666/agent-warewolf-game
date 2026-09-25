import type { ReactNode } from 'react';

import { cn } from '@/lib/cn';

interface FieldProps {
  label: ReactNode;
  help?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** label + 控件 + 帮助文字。整块是一个 <label>，点文字就能聚焦控件 */
export function Field({ label, help, className, children }: FieldProps) {
  return (
    <label className={cn('flex flex-col gap-1.5 text-13 text-dim', className)}>
      {label}
      {children}
      {help != null && (
        <small className="text-12 leading-normal text-faint [&_b]:font-medium [&_b]:text-gold-hi">
          {help}
        </small>
      )}
    </label>
  );
}
