import { useState } from 'react';

import type { GameEvent, Snapshot } from '@/api/types';
import { CardHead } from '@/components/ui/Card';
import { isWolfRole, passesFilter, type FeedFilter } from '@/lib/game';

import { FeedFilterChips } from './FeedFilterChips';
import { FeedItem } from './FeedItem';
import { SystemNote } from './SystemNote';
import { ThinkingBubble } from './ThinkingBubble';
import { useStickToBottom } from './useStickToBottom';

interface FeedCardProps {
  events: GameEvent[];
  snapshot: Snapshot;
  god: boolean;
}

/** 实况：事件流 + 频道筛选 + 「正在想」提示 + 回到最新 */
export function FeedCard({ events, snapshot, god }: FeedCardProps) {
  const [picked, setPicked] = useState<FeedFilter>('all');
  // 关掉上帝视角后，狼人频道 / 私聊不能再选
  const filter = !god && (picked === 'wolves' || picked === 'private') ? 'all' : picked;

  const cur = snapshot.current ?? {};
  const thinking = snapshot.status === 'running' && cur.seat ? cur : null;
  const { ref, onScroll, atBottom, scrollToBottom } = useStickToBottom<HTMLDivElement>(
    `${filter}:${events.length}:${thinking?.seat ?? ''}:${snapshot.status}`,
  );
  const bySeat = new Map(snapshot.players.map((p) => [p.seat, p]));

  const visible = events.flatMap((e, i) => {
    if (!passesFilter(e, filter)) return [];
    const p = e.actor ? bySeat.get(e.actor) : undefined;
    return [
      <FeedItem
        key={i}
        event={e}
        side={p?.role_cn ? (isWolfRole(p) ? 'wolf' : 'good') : undefined}
        agent={p?.agent}
        roleCn={god ? (p?.role_cn ?? undefined) : undefined}
      />,
    ];
  });

  return (
    <section
      aria-label="实况"
      className="relative flex h-[calc(100vh-212px)] min-h-[520px] min-w-0 flex-col overflow-hidden rounded-[20px] border border-line bg-card max-tablet:h-auto max-tablet:min-h-0 max-tablet:overflow-visible max-phone:rounded-none max-phone:border-0 max-phone:bg-transparent"
    >
      <div className="flex flex-col gap-3.5 border-b border-rule px-6 pt-5 pb-4 max-phone:border-0 max-phone:px-0 max-phone:pt-1 max-phone:pb-3">
        <CardHead
          title="实况"
          hint={events.length ? `${events.length} 条` : ''}
          className="max-phone:hidden"
        />
        <FeedFilterChips
          value={filter}
          god={god}
          onChange={(f) => {
            setPicked(f);
            scrollToBottom();
          }}
        />
      </div>

      <div
        ref={ref}
        onScroll={onScroll}
        className="flex flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-6 pt-4 pb-6 text-14 leading-[1.65] max-tablet:overflow-visible max-phone:p-0"
      >
        {visible.length === 0 && !thinking && (
          <p className="m-0 py-10 text-center text-faint">等待第一条事件…</p>
        )}
        {visible}
        {snapshot.status === 'failed' && (
          <SystemNote tone="god">{`引擎异常：\n${snapshot.error ?? ''}`}</SystemNote>
        )}
        {thinking?.seat && (
          <ThinkingBubble seat={thinking.seat} action={thinking.action_cn || thinking.action_type || ''} />
        )}
      </div>

      {!atBottom && (
        <button
          type="button"
          onClick={scrollToBottom}
          className="absolute bottom-4 left-1/2 h-9 -translate-x-1/2 rounded-full border border-gold bg-night px-4 text-13 text-gold-hi max-tablet:hidden"
        >
          回到最新
        </button>
      )}
    </section>
  );
}
