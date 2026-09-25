import type { GameEvent, Snapshot } from '@/api/types';
import { Hint } from '@/components/ui/Card';

import { FeedCard } from './feed/FeedCard';
import { StatusBar } from './StatusBar';
import { RoundTable } from './table/RoundTable';

interface LiveViewProps {
  snapshot: Snapshot | null;
  events: GameEvent[];
  god: boolean;
  onGodChange: (god: boolean) => void;
  onStop: () => void;
}

/** 第二步：对局实况（圆桌 + 事件流） */
export function LiveView({ snapshot, events, god, onGodChange, onStop }: LiveViewProps) {
  if (!snapshot) return <Hint className="block px-gutter py-10">正在接入对局…</Hint>;
  return (
    <section>
      <StatusBar snapshot={snapshot} god={god} onGodChange={onGodChange} onStop={onStop} />
      <div className="mx-auto grid max-w-[1560px] grid-cols-[minmax(0,1.3fr)_minmax(360px,1fr)] gap-7 px-gutter pt-7 pb-10 max-tablet:grid-cols-1 max-phone:gap-4 max-phone:px-4 max-phone:pt-2 max-phone:pb-[100px]">
        <RoundTable snapshot={snapshot} god={god} />
        <FeedCard events={events} snapshot={snapshot} god={god} />
      </div>
    </section>
  );
}
