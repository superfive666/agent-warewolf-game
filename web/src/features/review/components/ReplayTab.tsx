import type { Replay } from '@/api/types';

import { RevealCard } from './RevealCard';
import { Timeline } from './Timeline';

export function ReplayTab({ replay }: { replay: Replay }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_480px] items-start gap-8 max-laptop:grid-cols-[minmax(0,1fr)_400px] max-tablet:grid-cols-1 max-phone:gap-4">
      <Timeline replay={replay} />
      <RevealCard result={replay.result ?? {}} />
    </div>
  );
}
