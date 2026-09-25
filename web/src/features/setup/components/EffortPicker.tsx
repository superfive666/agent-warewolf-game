import { cn } from '@/lib/cn';
import { effortCn } from '@/lib/format';

interface EffortPickerProps {
  efforts: string[];
  value: string;
  disabled: boolean;
  label: string;
  onChange: (effort: string) => void;
}

export function EffortPicker({ efforts, value, disabled, label, onChange }: EffortPickerProps) {
  return (
    <div role="group" aria-label={label} className="grid grid-cols-5 gap-1">
      {efforts.map((e) => (
        <button
          key={e}
          type="button"
          title={e}
          disabled={disabled}
          aria-pressed={!disabled && value === e}
          onClick={() => onChange(e)}
          className={cn(
            'h-[30px] rounded-md border border-line bg-transparent p-0 text-12 text-dim max-phone:h-9',
            'aria-pressed:border-gold aria-pressed:bg-gold aria-pressed:font-bold aria-pressed:text-on-gold',
            'disabled:cursor-not-allowed disabled:opacity-35',
          )}
        >
          {effortCn(e)}
        </button>
      ))}
    </div>
  );
}
