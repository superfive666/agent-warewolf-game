import { useId, useState } from 'react';

import type { GameStatus, Replay } from '@/api/types';

import { RawTab } from './components/RawTab';
import { ReplayTab } from './components/ReplayTab';
import { ResultBanner } from './components/ResultBanner';
import { ReviewTabs, type TabDef } from './components/ReviewTabs';
import { SessionsTab } from './components/SessionsTab';
import { ThoughtsTab } from './components/ThoughtsTab';

type TabKey = 'replay' | 'thoughts' | 'sessions' | 'raw';

const TABS: readonly TabDef<TabKey>[] = [
  { key: 'replay', label: '战报' },
  { key: 'thoughts', label: '心路历程' },
  { key: 'sessions', label: '会话存档' },
  { key: 'raw', label: '原始数据' },
];

interface ReviewViewProps {
  gameId: string;
  replay: Replay;
  status: GameStatus | undefined;
  onAgain: () => void;
}

/** 第三步：复盘 */
export function ReviewView({ gameId, replay, status, onAgain }: ReviewViewProps) {
  const [tab, setTab] = useState<TabKey>('replay');
  const idPrefix = useId();
  const result = replay.result ?? {};

  return (
    <section>
      <ResultBanner replay={replay} status={status} onAgain={onAgain} />
      <ReviewTabs tabs={TABS} value={tab} onChange={setTab} idPrefix={idPrefix} />
      <div
        role="tabpanel"
        id={`${idPrefix}-panel-${tab}`}
        aria-labelledby={`${idPrefix}-tab-${tab}`}
        className="mx-auto max-w-[1560px] px-gutter pt-8 pb-16 max-phone:p-4 max-phone:pb-10"
      >
        {tab === 'replay' && <ReplayTab replay={replay} />}
        {tab === 'thoughts' && <ThoughtsTab thoughts={replay.thoughts ?? []} result={result} />}
        {tab === 'sessions' && <SessionsTab sessions={replay.sessions ?? []} result={result} />}
        {tab === 'raw' && <RawTab gameId={gameId} result={result} />}
      </div>
    </section>
  );
}
