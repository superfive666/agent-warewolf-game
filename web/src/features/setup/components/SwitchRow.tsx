import { Switch } from '@/components/ui/Switch';

interface SwitchRowProps {
  title: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function SwitchRow({ title, description, checked, onChange }: SwitchRowProps) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 border-t border-rule py-3 last:border-b">
      <span className="flex flex-col gap-0.5">
        <b className="text-15 font-normal">{title}</b>
        <small className="text-12 text-dim">{description}</small>
      </span>
      <Switch checked={checked} onChange={onChange} />
    </label>
  );
}
