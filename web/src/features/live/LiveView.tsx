import type { GameEvent, Snapshot } from '@/api/types';
import { Hint } from '@/components/ui/Card';

import { FeedCard } from './feed/FeedCard';
import { HumanPanel } from './human/HumanPanel';
import { useHumanSeat } from './human/useHumanSeat';
import { StatusBar } from './StatusBar';
import { RoundTable } from './table/RoundTable';

interface LiveViewProps {
  gameId: string;
  snapshot: Snapshot | null;
  events: GameEvent[];
  god: boolean;
  onGodChange: (god: boolean) => void;
  onStop: () => void;
}

/** 第二步：对局实况（圆桌 + 事件流）。本机坐着真人座位时，上方多一块操作面板 */
export function LiveView({ gameId, snapshot, events, god, onGodChange, onStop }: LiveViewProps) {
  const { seat, submit } = useHumanSeat(gameId);
  if (!snapshot) return <Hint className="block px-gutter py-10">正在接入对局…</Hint>;
  // 有真人的对局，服务端在结束前不给上帝视角；这里同步关掉开关，避免界面显示和数据不一致
  const godOn = god && !snapshot.god_locked;
  return (
    <section>
      <StatusBar snapshot={snapshot} god={godOn} onGodChange={onGodChange} onStop={onStop} />
      {seat && (
        <div className="mx-auto max-w-[1560px] px-gutter pt-7 max-phone:px-4 max-phone:pt-2">
          <HumanPanel seat={seat} onSubmit={submit} />
        </div>
      )}
      <div className="mx-auto grid max-w-[1560px] grid-cols-[minmax(0,1.3fr)_minmax(360px,1fr)] gap-7 px-gutter pt-7 pb-10 max-tablet:grid-cols-1 max-phone:gap-4 max-phone:px-4 max-phone:pt-2 max-phone:pb-[100px]">
        <RoundTable snapshot={snapshot} god={godOn} />
        <FeedCard events={events} snapshot={snapshot} god={godOn} />
      </div>
    </section>
  );
}
