import type { FormOption } from '@/api/types';
import { Chip } from '@/components/ui/Chip';

interface OptionChipsProps {
  label: string;
  options: FormOption[];
  /** 单选：当前值；多选：已选的值 */
  selected: (value: FormOption['value']) => boolean;
  onToggle: (value: FormOption['value']) => void;
  /** 多选达到上限时，没选中的都禁用 */
  full?: boolean;
}

/** 一排可点的选项（座位号、是 / 否、宣称身份……） */
export function OptionChips({ label, options, selected, onToggle, full }: OptionChipsProps) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((o) => {
        const on = selected(o.value);
        return (
          <Chip key={String(o.value)} active={on} disabled={full && !on} onClick={() => onToggle(o.value)}>
            {o.label}
          </Chip>
        );
      })}
    </div>
  );
}
