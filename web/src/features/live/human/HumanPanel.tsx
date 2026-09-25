import type { ActionPayload, SeatView } from '@/api/types';

import { ActionForm } from './ActionForm';
import { privateEvents } from './model';
import { PrivateLog } from './PrivateLog';
import { SeatIdentity } from './SeatIdentity';

interface HumanPanelProps {
  seat: SeatView;
  onSubmit: (requestId: number, action: ActionPayload) => Promise<void>;
}

/** 真人玩家的座位面板：左边是底牌和私密消息，右边是轮到你时的操作 */
export function HumanPanel({ seat, onSubmit }: HumanPanelProps) {
  const { identity } = seat.view;
  const running = seat.status === 'running' || seat.status === 'pending';
  return (
    <section
      aria-label="你的座位"
      className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] gap-7 rounded-[20px] border border-gold-line bg-card p-6 max-tablet:grid-cols-1 max-phone:gap-4 max-phone:rounded-[14px] max-phone:p-4"
    >
      <div className="flex flex-col gap-5">
        <SeatIdentity identity={identity} knowledge={seat.knowledge_cn} />
        <PrivateLog events={privateEvents(seat.view.timeline)} />
      </div>
      {/* 窄屏上下叠放时，操作放在最上面，轮到你时不用往下翻 */}
      <div className="flex flex-col justify-center max-tablet:order-first">
        {seat.pending?.form ? (
          <ActionForm key={seat.pending.request_id} pending={seat.pending} onSubmit={onSubmit} />
        ) : (
          <p className="m-0 text-center text-14 text-dim">
            {!running
              ? '对局已结束'
              : seat.released
                ? '你已出局，可以继续旁观公开发言'
                : '等待其他玩家行动……轮到你时这里会出现操作'}
          </p>
        )}
      </div>
    </section>
  );
}
