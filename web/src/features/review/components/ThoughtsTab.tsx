import type { GameResult, Thought } from '@/api/types';
import { Hint } from '@/components/ui/Card';
import { agentLabel } from '@/lib/game';

import { SeatAccordion } from './SeatAccordion';
import { ThoughtEntry } from './ThoughtEntry';

function groupBySeat(thoughts: Thought[]): [number, Thought[]][] {
  const map = new Map<number, Thought[]>();
  for (const t of thoughts) map.set(t.seat, [...(map.get(t.seat) ?? []), t]);
  return [...map.entries()].sort(([a], [b]) => a - b);
}

export function ThoughtsTab({ thoughts, result }: { thoughts: Thought[]; result: GameResult }) {
  const groups = groupBySeat(thoughts);
  return (
    <>
      <Hint className="mb-4 block">
        每个 agent 在每个决策点的内心想法。这些内容从未进入过任何其他玩家的视角。
      </Hint>
      {!groups.length && <Hint className="block">（这一局没有记录到心路历程）</Hint>}
      {groups.map(([seat, list], idx) => (
        <SeatAccordion
          key={seat}
          seat={seat}
          result={result}
          title={`${seat} 号 · ${result.roles_cn?.[String(seat)] ?? ''}`}
          subtitle={[agentLabel(result, seat), `${list.length} 条`].filter(Boolean).join(' · ')}
          defaultOpen={idx === 0}
        >
          {list.map((t, i) => (
            <ThoughtEntry key={i} thought={t} />
          ))}
        </SeatAccordion>
      ))}
    </>
  );
}
