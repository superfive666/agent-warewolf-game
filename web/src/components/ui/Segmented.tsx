import { cn } from '@/lib/cn';

interface SegmentedProps<T extends string> {
  value: T;
  options: readonly (readonly [T, string])[];
  onChange: (value: T) => void;
  label: string;
}

export function Segmented<T extends string>({ value, options, onChange, label }: SegmentedProps<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="grid auto-cols-fr grid-flow-col gap-1 rounded-[10px] border border-line bg-inset p-1"
    >
      {options.map(([v, text]) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={v === value}
          onClick={() => onChange(v)}
          className={cn(
            'h-9 rounded-[7px] border-none bg-transparent text-14 text-dim',
            'aria-checked:bg-raised aria-checked:font-medium aria-checked:text-gold-hi',
          )}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
