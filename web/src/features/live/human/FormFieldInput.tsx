import type { FormField } from '@/api/types';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';

import type { CheckValue, FieldValue } from './model';
import { OptionChips } from './OptionChips';

interface FormFieldInputProps {
  field: FormField;
  value: FieldValue;
  onChange: (value: FieldValue) => void;
}

/** 按字段类型渲染一个输入控件，外面包一层标题和说明 */
export function FormFieldInput({ field: f, value, onChange }: FormFieldInputProps) {
  const opts = f.options ?? [];
  let control;
  if (f.kind === 'choice') {
    control = (
      <OptionChips label={f.label} options={opts} selected={(v) => v === value} onToggle={onChange} />
    );
  } else if (f.kind === 'multi') {
    const picked = (value as number[] | undefined) ?? [];
    control = (
      <OptionChips
        label={f.label}
        options={opts}
        selected={(v) => picked.includes(v as number)}
        full={!!f.max_items && picked.length >= f.max_items}
        onToggle={(v) =>
          onChange(picked.includes(v as number) ? picked.filter((x) => x !== v) : [...picked, v as number])
        }
      />
    );
  } else if (f.kind === 'check') {
    const c = (value as CheckValue | undefined) ?? { target: null, result: null };
    control = (
      <div className="flex flex-col gap-2">
        <OptionChips
          label={`${f.label}：座位`}
          options={opts}
          selected={(v) => v === c.target}
          onToggle={(v) => onChange({ ...c, target: v === c.target ? null : (v as number) })}
        />
        <OptionChips
          label={`${f.label}：结果`}
          options={f.results ?? []}
          selected={(v) => v === c.result}
          onToggle={(v) => onChange({ ...c, result: v === c.result ? null : (v as string) })}
        />
      </div>
    );
  } else if (f.kind === 'textarea') {
    const text = typeof value === 'string' ? value : '';
    control = (
      <Textarea
        aria-label={f.label}
        rows={5}
        value={text}
        placeholder="说点什么……"
        onChange={(e) => onChange(e.target.value)}
      />
    );
  } else {
    control = (
      <Input
        aria-label={f.label}
        value={typeof value === 'string' ? value : ''}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  const count =
    f.kind === 'textarea' && f.max_chars ? `${String(value ?? '').length} / ${f.max_chars}` : null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline gap-2">
        <b className="text-14 font-medium text-fg">{f.label}</b>
        {count && <span className="ml-auto text-12 text-faint tabular-nums">{count}</span>}
      </div>
      {control}
      {f.desc && <small className="text-12 leading-normal text-faint">{f.desc}</small>}
    </div>
  );
}
