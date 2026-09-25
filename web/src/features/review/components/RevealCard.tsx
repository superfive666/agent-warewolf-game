import type { GameResult } from '@/api/types';
import { Card, CardTitle } from '@/components/ui/Card';
import { RolePill } from '@/components/ui/RolePill';
import { cn } from '@/lib/cn';
import { revealRows, revealTone } from '@/lib/game';

/** 身份揭晓：每个座位的真实身份、所用 agent、结局 */
export function RevealCard({ result }: { result: GameResult }) {
  return (
    <Card className="sticky top-[152px] gap-3 px-6 py-[22px] max-tablet:static max-phone:p-4">
      <CardTitle>身份揭晓</CardTitle>
      <div>
        {revealRows(result).map((p) => (
          <div
            key={p.seat}
            className={cn(
              'grid min-h-10 grid-cols-[44px_76px_minmax(0,1fr)_auto] items-center gap-2.5 border-t border-line-soft',
              'max-phone:grid-cols-[40px_64px_minmax(0,1fr)] max-phone:gap-y-0 max-phone:py-2',
              !p.alive && 'opacity-72',
            )}
          >
            <span className="font-serif font-bold">{p.seat} 号</span>
            <RolePill
              tone={revealTone(p)}
              className="justify-self-start px-2.5 py-0.5 text-12 max-phone:px-2.5 max-phone:py-0.5"
            >
              {p.role_cn || p.role || ''}
            </RolePill>
            <span
              title={p.agent ?? ''}
              className="truncate text-13 whitespace-nowrap text-dim max-phone:col-start-3 max-phone:row-start-1"
            >
              {p.agent ?? ''}
            </span>
            <span
              className={cn(
                'text-right text-12 text-dim max-phone:col-start-3 max-phone:text-left',
                p.alive && 'text-gold-hi',
              )}
            >
              {p.fate_cn || (p.alive ? '存活' : p.died_cause_cn || '出局')}
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}
