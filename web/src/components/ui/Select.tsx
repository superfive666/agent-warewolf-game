import type { SelectHTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export type SelectOption = readonly [value: string, label: string];

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'onChange'> {
  options: readonly SelectOption[];
  onChange?: (value: string) => void;
}

export function Select({ options, onChange, className, ...rest }: SelectProps) {
  return (
    <select
      className={cn('form-control select-chevron not-disabled:cursor-pointer', className)}
      onChange={(e) => onChange?.(e.target.value)}
      {...rest}
    >
      {options.map(([v, label]) => (
        <option key={v} value={v}>
          {label}
        </option>
      ))}
    </select>
  );
}
