import type { GameListEntry } from '@/api/types';
import { Medal } from '@/components/ui/Medal';
import { cn } from '@/lib/cn';
import { fmtCreatedAt, statusCn } from '@/lib/format';

function playerCount(g: GameListEntry): number | null {
  const n = g.n_players ?? g.config?.n_players ?? (g.board?.name ? parseInt(g.board.name, 10) : NaN);
  return Number.isFinite(n) ? n : null;
}

export function HistoryRow({ game: g, onOpen }: { game: GameListEntry; onOpen: () => void }) {
  const n = playerCount(g);
  const winner = g.winner_cn || (g.winner === 'VILLAGE' ? '好人阵营' : g.winner ? '狼人阵营' : '');
  return (
    <button
      type="button"
      onClick={onOpen}
      className="flex min-h-16 w-full items-center gap-3 rounded-lg border-0 border-b border-line-soft bg-transparent p-2 text-left hover:bg-raised"
    >
      <Medal>{n ?? '?'}</Medal>
      <span className="flex min-w-0 flex-1 flex-col">
        <b>
          {n ? `${n} 人局 · ` : ''}
          {statusCn(g.status)}
        </b>
        <small className="text-12 text-dim">
          {fmtCreatedAt(g.created_at)} · {String(g.id).slice(0, 6)}
          {g.days ? ` · ${g.days} 天` : ''}
        </small>
      </span>
      {winner && (
        <span
          className={cn(
            'text-13 whitespace-nowrap',
            g.winner === 'VILLAGE' ? 'text-gold-hi' : 'text-wolf-fg',
          )}
        >
          {winner}胜
        </span>
      )}
    </button>
  );
}
