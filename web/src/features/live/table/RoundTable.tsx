import type { Snapshot } from '@/api/types';
import { PHONE_QUERY, useMediaQuery } from '@/hooks/useMediaQuery';

import { ringPosition } from './ringLayout';
import { SeatToken } from './SeatToken';
import { TableCenter } from './TableCenter';
import { TableLegend } from './TableLegend';

interface RoundTableProps {
  snapshot: Snapshot;
  god: boolean;
}

export function RoundTable({ snapshot, god }: RoundTableProps) {
  const compact = useMediaQuery(PHONE_QUERY);
  const cur = snapshot.current ?? {};
  const n = snapshot.players.length;

  return (
    <section
      aria-label="圆桌"
      className="flex min-w-0 flex-col gap-2 rounded-[20px] border border-line bg-table p-4 max-phone:rounded-[18px] max-phone:p-1.5"
    >
      <div className="relative mx-auto aspect-[10/11] max-h-[calc(100vh-250px)] min-h-[340px] w-full max-tablet:max-h-none max-phone:aspect-[358/412] max-phone:min-h-0">
        <div
          aria-hidden="true"
          className="absolute top-[47%] left-1/2 h-[54%] w-[52%] -translate-1/2 rounded-[50%] border-[1.5px] border-gold-line bg-page shadow-[inset_0_0_0_12px_var(--color-page),inset_0_0_0_13px_var(--color-gold-dark)] max-phone:h-1/2 max-phone:w-[48%]"
        />
        <TableCenter snapshot={snapshot} />
        {snapshot.players.map((p, i) => (
          <SeatToken
            key={p.seat}
            player={p}
            active={snapshot.status === 'running' && cur.seat === p.seat}
            activeLabel={cur.action_cn || '行动中'}
            style={ringPosition(i, n, compact)}
          />
        ))}
      </div>
      <TableLegend god={god} />
    </section>
  );
}
