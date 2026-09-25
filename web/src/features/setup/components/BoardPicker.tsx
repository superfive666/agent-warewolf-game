import type { BoardInfo } from '@/api/types';
import { cn } from '@/lib/cn';

interface BoardPickerProps {
  boards: Record<string, BoardInfo>;
  value: number;
  onChange: (n: number) => void;
}

export function BoardPicker({ boards, value, onChange }: BoardPickerProps) {
  const sizes = Object.keys(boards)
    .map(Number)
    .sort((a, b) => a - b);
  return (
    <div role="radiogroup" aria-label="人数" className="grid grid-cols-5 gap-3 max-phone:gap-1.5">
      {sizes.map((n) => {
        const b = boards[String(n)];
        const on = n === value;
        return (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(n)}
            className={cn(
              'flex h-[88px] flex-col items-center justify-center gap-1 rounded-xl border border-line bg-inset text-fg max-phone:h-15',
              on &&
                'border-[1.5px] border-gold bg-gold-bg text-gold-hi shadow-[0_0_0_4px_rgba(214,178,94,.12)]',
            )}
          >
            <b className="font-serif text-26 max-phone:text-20">
              {n}
              <small className="ml-0.5 text-14 max-phone:text-11">人</small>
            </b>
            {b && (
              <span className={cn('text-12 text-dim max-phone:hidden', on && 'text-gold-soft')}>
                {b.wolves}狼 · {b.gods}神 · {b.villagers}民
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
