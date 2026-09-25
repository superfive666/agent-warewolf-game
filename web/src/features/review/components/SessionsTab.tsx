import type { AgentSession, GameResult } from '@/api/types';
import { Hint } from '@/components/ui/Card';

import { SeatAccordion } from './SeatAccordion';
import { SessionEntry } from './SessionEntry';

export function SessionsTab({ sessions, result }: { sessions: AgentSession[]; result: GameResult }) {
  return (
    <>
      <Hint className="mb-4 block">
        每个座位的 agent
        会话。玩家离场时容器/进程会被销毁，但会话在销毁之前就已经存进会话库，所以这里始终是完整的。
      </Hint>
      {!sessions.length && <Hint className="block">（这一局没有会话记录）</Hint>}
      {sessions.map((s) => (
        <SeatAccordion
          key={s.seat}
          seat={s.seat}
          result={result}
          title={`${s.seat} 号 · ${s.role_cn || result.roles_cn?.[String(s.seat)] || s.role || ''}`}
          subtitle={`${(s.messages ?? []).length} 条消息`}
        >
          <SessionEntry session={s} />
        </SeatAccordion>
      ))}
    </>
  );
}
