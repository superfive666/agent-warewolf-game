import { useEffect, useState } from 'react';

import { api } from '@/api/games';
import type { GameListEntry } from '@/api/types';
import { Hint } from '@/components/ui/Card';
import { Sheet } from '@/components/ui/Sheet';

import { HistoryRow } from './HistoryRow';

type LoadState =
  { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; games: GameListEntry[] };

interface HistoryDialogProps {
  open: boolean;
  onClose: () => void;
  onOpenGame: (id: string) => void;
}

/** 历史对局：内存里正在跑的 + 会话库里的。每次打开都重新拉 */
export function HistoryDialog({ open, onClose, onOpenGame }: HistoryDialogProps) {
  return (
    <Sheet open={open} title="历史对局" onClose={onClose}>
      {open && <HistoryList onOpenGame={onOpenGame} />}
    </Sheet>
  );
}

function HistoryList({ onOpenGame }: { onOpenGame: (id: string) => void }) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' });

  useEffect(() => {
    const ctl = new AbortController();
    api
      .listGames(ctl.signal)
      .then((data) => {
        const games = [...(data.live ?? []), ...(data.past ?? [])].sort((a, b) =>
          String(b.created_at).localeCompare(String(a.created_at)),
        );
        setState({ kind: 'ready', games });
      })
      .catch((e: unknown) => {
        if (!ctl.signal.aborted)
          setState({ kind: 'error', message: e instanceof Error ? e.message : String(e) });
      });
    return () => ctl.abort();
  }, []);

  return (
    <div className="flex flex-col px-4 pt-2 pb-4">
      {state.kind === 'loading' && <Hint>加载中…</Hint>}
      {state.kind === 'error' && <Hint>加载失败：{state.message}</Hint>}
      {state.kind === 'ready' && !state.games.length && <Hint>还没有对局记录。</Hint>}
      {state.kind === 'ready' &&
        state.games.map((g) => <HistoryRow key={g.id} game={g} onOpen={() => onOpenGame(g.id)} />)}
    </div>
  );
}
