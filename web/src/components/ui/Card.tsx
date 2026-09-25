import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/cn';

export function Card({ className, ...rest }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        'flex flex-col gap-5 rounded-2xl border border-line bg-card p-7',
        'max-phone:gap-3.5 max-phone:rounded-[14px] max-phone:p-4',
        className,
      )}
      {...rest}
    />
  );
}

export function CardTitle({ className, ...rest }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('text-21 font-bold text-gold-hi max-phone:text-18', className)} {...rest} />;
}

interface CardHeadProps {
  title: ReactNode;
  hint?: ReactNode;
  className?: string;
}

export function CardHead({ title, hint, className }: CardHeadProps) {
  return (
    <div className={cn('flex flex-wrap items-baseline gap-3', className)}>
      <CardTitle>{title}</CardTitle>
      {hint != null && <Hint>{hint}</Hint>}
    </div>
  );
}

export function Hint({ className, ...rest }: HTMLAttributes<HTMLElement>) {
  return <span className={cn('text-13 text-dim', className)} {...rest} />;
}
