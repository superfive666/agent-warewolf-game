import type { GameStatus, Replay } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Eyebrow } from '@/components/ui/Eyebrow';
import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';
import { downloadText } from '@/lib/download';

import { ResultStats } from './ResultStats';

interface ResultBannerProps {
  replay: Replay;
  status: GameStatus | undefined;
  onAgain: () => void;
}

export function ResultBanner({ replay, status, onAgain }: ResultBannerProps) {
  const res = replay.result ?? {};
  const village = res.winner === 'VILLAGE';
  const wolf = !village && !!res.winner;

  return (
    <div className="relative flex items-center gap-9 overflow-hidden border-b border-line bg-banner px-gutter py-10 max-phone:flex-col max-phone:gap-2 max-phone:px-4 max-phone:pt-7 max-phone:pb-6 max-phone:text-center">
      {/* 右侧的同心圆装饰 */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 -right-[60px] size-[300px] -translate-y-1/2 rounded-full shadow-[0_0_0_1px_var(--color-switch),inset_0_0_0_40px_var(--color-banner),inset_0_0_0_41px_var(--color-switch),inset_0_0_0_80px_var(--color-banner),inset_0_0_0_81px_var(--color-switch)] max-phone:hidden"
      />
      <span className="relative z-1 flex h-[136px] w-[120px] flex-none items-center justify-center max-phone:h-[82px] max-phone:w-[72px]">
        <Icon
          name="shield"
          bare
          className={cn(
            'absolute inset-0 size-full fill-raised stroke-gold stroke-[.6]',
            wolf && 'stroke-wolf',
          )}
        />
        <Icon
          name={village ? 'sun' : 'wolf'}
          className={cn(
            'relative size-12 stroke-[1.3] text-gold-hi max-phone:size-[30px]',
            wolf && 'text-wolf-fg',
          )}
        />
      </span>

      <div className="relative z-1 flex min-w-0 flex-1 flex-col gap-2">
        <Eyebrow className={cn(wolf && 'text-wolf')}>
          {village ? 'THE VILLAGE PREVAILS' : res.winner ? 'THE WOLVES PREVAIL' : 'THE NIGHT ENDS'}
        </Eyebrow>
        <h1
          className={cn(
            'text-46 font-black tracking-[4px] text-gold-hi max-phone:text-32 max-phone:tracking-[3px]',
            wolf && 'text-wolf-fg',
          )}
        >
          {(res.winner_cn || '平局') + (res.winner ? '胜利' : '')}
        </h1>
        <p className="m-0 text-16 text-vil-fg max-phone:text-14">
          {res.reason || (status === 'stopped' ? '对局被中止' : '')}
        </p>
        <ResultStats replay={replay} />
      </div>

      <div className="relative z-1 flex w-[220px] flex-col gap-2.5 max-phone:mt-3 max-phone:w-full max-phone:flex-row">
        <Button
          variant="primary"
          onClick={onAgain}
          className="max-phone:flex-1 max-phone:px-2.5 max-phone:text-13"
        >
          <Icon name="redo" />
          再来一局
        </Button>
        <Button
          variant="outline"
          onClick={() => downloadText('replay.md', replay.markdown ?? '', 'text/markdown')}
          className="max-phone:flex-1 max-phone:px-2.5 max-phone:text-13"
        >
          <Icon name="down" />
          下载战报 Markdown
        </Button>
      </div>
    </div>
  );
}
