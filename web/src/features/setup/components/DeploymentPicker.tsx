import { cn } from '@/lib/cn';
import { splitDesc } from '@/lib/format';

interface DeploymentPickerProps {
  deployments: Record<string, string>;
  value: string;
  onChange: (key: string) => void;
}

export function DeploymentPicker({ deployments, value, onChange }: DeploymentPickerProps) {
  return (
    <div role="radiogroup" aria-label="部署模式" className="grid grid-cols-2 gap-2">
      {Object.entries(deployments).map(([key, desc]) => (
        <button
          key={key}
          type="button"
          role="radio"
          aria-checked={key === value}
          title={desc}
          onClick={() => onChange(key)}
          className={cn(
            'min-h-11 rounded-lg border border-line bg-transparent px-2 py-1.5 text-13 text-vil-fg',
            'aria-checked:border-gold aria-checked:bg-gold-bg aria-checked:text-gold-hi',
          )}
        >
          {splitDesc(desc)[0]}
        </button>
      ))}
    </div>
  );
}
