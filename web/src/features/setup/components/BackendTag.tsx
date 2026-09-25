import { cn } from '@/lib/cn';

const TONES: Record<string, string> = {
  claude: 'border-gold-line text-gold-hi',
  openai: 'border-good-line text-good-fg',
};

export function BackendTag({ backend, label }: { backend: string; label: string }) {
  return (
    <span
      className={cn(
        'rounded-md border border-vil-line px-2 py-0.5 text-12 whitespace-nowrap text-vil-fg',
        TONES[backend],
      )}
    >
      {label}
    </span>
  );
}
