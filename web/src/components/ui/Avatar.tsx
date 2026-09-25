import { cn } from '@/lib/cn';

export type Side = 'wolf' | 'good';

interface AvatarProps {
  seat: number;
  side?: Side | undefined;
  className?: string;
}

/** 圆形座位号：实况气泡、复盘手风琴都用 */
export function Avatar({ seat, side, className }: AvatarProps) {
  return (
    <span
      className={cn(
        'flex size-9 flex-none items-center justify-center rounded-full border-[1.5px] border-seat-ring',
        'font-serif text-15 font-bold',
        side === 'wolf' && 'border-wolf',
        side === 'good' && 'border-good',
        className,
      )}
    >
      {seat}
    </span>
  );
}
