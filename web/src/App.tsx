import { useState } from 'react';

import { api } from '@/api/games';
import { TopBar } from '@/components/layout/TopBar';
import { useToast } from '@/components/toast/useToast';
import { useGameSession } from '@/features/game/useGameSession';
import { HistoryDialog } from '@/features/history/HistoryDialog';
import { LiveView } from '@/features/live/LiveView';
import { ReviewView } from '@/features/review/ReviewView';
import { SetupView } from '@/features/setup/SetupView';
import { useHashGameId } from '@/hooks/useHashRoute';
import type { View } from '@/lib/view';

/**
 * 顶层只做三件事：路由（hash 里的对局 id）、当前在哪一步、把对局数据分发给各视图。
 */
export function App() {
  const toast = useToast();
  const [gameId, navigate] = useHashGameId();
  const [view, setView] = useState<View>(gameId ? 'live' : 'setup');
  const [god, setGod] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  // hash 里换了一局 → 切到对局页（渲染期间根据 props 调整 state，而不是写 effect）
  const [attachedId, setAttachedId] = useState(gameId);
  if (gameId !== attachedId) {
    setAttachedId(gameId);
    if (gameId) setView('live');
  }

  const { snapshot, events, replay } = useGameSession(gameId, god, {
    onNotFound: () => {
      toast('找不到这局对局（可能是服务重启前的对局）');
      navigate(null, { replace: true });
      setView('setup');
    },
    // 看着它跑完的：自动翻到复盘；中途切走了就不打扰
    onFinished: () => setView((v) => (v === 'live' ? 'review' : v)),
  });

  const go = (v: View) => {
    setView(v);
    window.scrollTo({ top: 0 });
  };

  const stop = () => {
    if (gameId) api.stopGame(gameId).catch((e: unknown) => toast(`中止失败：${String(e)}`));
  };

  return (
    <>
      <TopBar
        view={view}
        gameId={gameId}
        hasReplay={!!replay}
        onNavigate={go}
        onOpenHistory={() => setHistoryOpen(true)}
      />
      <main>
        <SetupView hidden={view !== 'setup'} onStarted={(id) => navigate(id)} />
        {view === 'live' && gameId && (
          <LiveView snapshot={snapshot} events={events} god={god} onGodChange={setGod} onStop={stop} />
        )}
        {view === 'review' && gameId && replay && (
          <ReviewView gameId={gameId} replay={replay} status={snapshot?.status} onAgain={() => go('setup')} />
        )}
      </main>
      <HistoryDialog
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        onOpenGame={(id) => {
          setHistoryOpen(false);
          if (id === gameId) go(replay ? 'review' : 'live');
          else navigate(id);
        }}
      />
    </>
  );
}
