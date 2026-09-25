import type { CSSProperties } from 'react';

import type { SnapshotPlayer } from '@/api/types';
import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';
import { isWolfRole, seatRoleLine } from '@/lib/game';

interface SeatTokenProps {
  player: SnapshotPlayer;
  active: boolean;
  activeLabel: string;
  style: CSSProperties;
}

export function SeatToken({ player: p, active, activeLabel, style }: SeatTokenProps) {
  const side = p.role_cn ? (isWolfRole(p) ? 'wolf' : 'good') : null;
  const line = seatRoleLine(p);
  const roleText = active ? activeLabel : line.text;
  const roleColor =
    active || line.claimed
      ? 'text-gold-hi'
      : side === 'good'
        ? 'text-good-fg'
        : side === 'wolf'
          ? 'text-wolf-fg'
          : 'text-dim';

  return (
    <div
      style={style}
      className={cn(
        'absolute -mt-9 -ml-14 flex w-28 flex-col items-center gap-1 text-center transition-opacity',
        'max-phone:-mt-6 max-phone:-ml-8 max-phone:w-16 max-phone:gap-[3px]',
        !p.alive && 'opacity-45',
      )}
    >
      <div
        className={cn(
          'relative flex size-[72px] items-center justify-center rounded-full border-2 border-seat-ring bg-disc',
          'font-serif text-26 font-bold transition-[border-color,box-shadow]',
          'max-phone:size-12 max-phone:border-[1.5px] max-phone:text-18',
          side === 'wolf' && 'border-wolf',
          side === 'good' && 'border-good',
          !p.alive && 'dead-cross border-seat-dead',
          active && [
            'border-gold-hi bg-active-disc text-gold-hi',
            'shadow-[0_0_0_7px_rgba(15,26,54,1),0_0_0_8px_var(--color-gold-hi),0_0_28px_rgba(240,212,138,.45)]',
            'max-phone:shadow-[0_0_0_4px_rgba(15,26,54,1),0_0_0_5px_var(--color-gold-hi),0_0_16px_rgba(240,212,138,.5)]',
          ],
        )}
      >
        {p.seat}
        {p.is_sheriff && (
          <span
            title="警长"
            className="absolute -top-1.5 -right-1.5 flex size-[26px] items-center justify-center rounded-full border-2 border-table bg-gold text-on-gold max-phone:-top-[5px] max-phone:-right-[5px] max-phone:size-5"
          >
            <Icon name="star" bare className="size-3.5 fill-current max-phone:size-[11px]" />
          </span>
        )}
      </div>
      <span
        title={p.agent ?? ''}
        className="max-w-28 truncate text-12 whitespace-nowrap text-dim max-phone:hidden"
      >
        {p.agent ?? ''}
      </span>
      <span
        className={cn(
          'text-13 font-medium whitespace-nowrap max-phone:max-w-[70px] max-phone:truncate max-phone:text-11 max-phone:font-normal',
          roleColor,
        )}
      >
        {roleText || ' '}
      </span>
    </div>
  );
}
