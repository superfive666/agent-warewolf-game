import { useEffect, useState } from 'react';

import { api } from '@/api/games';
import type { GameResult } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Hint } from '@/components/ui/Card';
import { Icon } from '@/components/ui/Icon';
import { Pre } from '@/components/ui/Pre';
import { downloadText } from '@/lib/download';

const pretty = (v: unknown) => JSON.stringify(v, null, 2);

export function RawTab({ gameId, result }: { gameId: string; result: GameResult }) {
  // 逐座位视角只有内存里的对局才有；历史对局 404 → 不显示下载按钮
  const [views, setViews] = useState<{ gameId: string; data: unknown } | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    api
      .views(gameId, ctl.signal)
      .then((data) => setViews({ gameId, data }))
      .catch(() => undefined);
    return () => ctl.abort();
  }, [gameId]);

  const viewsData = views?.gameId === gameId ? views.data : null;
  const resultJson = pretty(result);

  return (
    <>
      <Hint className="block">下面是这局的全部视角上下文（每个座位一份 + 狼队一份）和完整结果。</Hint>
      <div className="mt-3 mb-4 flex flex-wrap gap-2.5">
        {viewsData != null && (
          <Button
            variant="outline"
            onClick={() => downloadText('views.json', pretty(viewsData), 'application/json')}
          >
            <Icon name="down" />
            下载全部视角
          </Button>
        )}
        <Button variant="outline" onClick={() => downloadText('result.json', resultJson, 'application/json')}>
          <Icon name="down" />
          下载结果
        </Button>
      </div>
      <Pre>{resultJson}</Pre>
    </>
  );
}
