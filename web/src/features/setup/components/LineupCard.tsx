import type { Options } from '@/api/types';
import { Card, CardHead } from '@/components/ui/Card';

import type { SeatConfig } from '../model';

import { BulkApply } from './BulkApply';
import { SeatCard } from './SeatCard';

interface LineupCardProps {
  options: Options;
  seats: SeatConfig[];
  onSeatChange: (index: number, patch: Partial<SeatConfig>) => void;
  onApplyAll: (seat: SeatConfig) => void;
}

export function LineupCard({ options, seats, onSeatChange, onApplyAll }: LineupCardProps) {
  return (
    <Card>
      <CardHead title="座位阵容" hint="每个座位单独选后端、模型与思考强度" />
      <BulkApply options={options} onApply={onApplyAll} />
      <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3.5 max-phone:grid-cols-1 max-phone:gap-0 max-phone:overflow-hidden max-phone:rounded-[14px] max-phone:border max-phone:border-line max-phone:bg-card">
        {seats.map((seat, i) => (
          <SeatCard
            // 座位就是按位置区分的，用下标当 key 正合适
            key={i}
            index={i}
            seat={seat}
            options={options}
            onChange={(patch) => onSeatChange(i, patch)}
          />
        ))}
      </div>
    </Card>
  );
}
