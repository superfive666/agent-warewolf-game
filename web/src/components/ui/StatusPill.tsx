import type { GameStatus } from '@/api/types';
import { cn } from '@/lib/cn';
import { statusCn } from '@/lib/format';

const TONES: Partial<Record<GameStatus, string>> = {
  running: 'border-ok-line bg-ok-bg text-ok-fg',
  finished: 'border-gold-line bg-gold-bg text-gold-hi',
  failed: 'border-wolf-line bg-wolf-bg text-wolf-fg',
  stopped: 'border-wolf-line bg-wolf-bg text-wolf-fg',
};

export function StatusPill({ status, className }: { status: GameStatus; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border border-line bg-raised px-3.5 py-1.5',
        'text-13 font-medium whitespace-nowrap text-dim',
        TONES[status],
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'size-2 rounded-full bg-current',
          status === 'running' && 'animate-pulse-soft shadow-[0_0_0_4px_rgba(159,224,200,.18)]',
        )}
      />
      {statusCn(status)}
    </span>
  );
}
