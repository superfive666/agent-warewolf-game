import type { Snapshot } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Eyebrow } from '@/components/ui/Eyebrow';
import { Icon } from '@/components/ui/Icon';
import { StatusPill } from '@/components/ui/StatusPill';
import { Switch } from '@/components/ui/Switch';
import { cn } from '@/lib/cn';
import { isNight, roman } from '@/lib/format';

interface StatusBarProps {
  snapshot: Snapshot;
  god: boolean;
  onGodChange: (god: boolean) => void;
  onStop: () => void;
}

export function StatusBar({ snapshot: s, god, onGodChange, onStop }: StatusBarProps) {
  const night = isNight(s.phase);
  const phase = s.phase_cn || s.phase;
  const cur = s.current ?? {};
  const running = s.status === 'running';
  const locked = !!s.god_locked;

  return (
    <div className="flex min-h-[72px] flex-wrap items-center gap-5 border-b border-line-soft px-gutter py-3 max-phone:grid max-phone:grid-cols-[1fr_auto] max-phone:gap-1.5 max-phone:border-0 max-phone:px-4 max-phone:pt-3.5 max-phone:pb-1.5">
      <StatusPill
        status={s.status}
        className="max-phone:col-start-2 max-phone:row-start-1 max-phone:justify-self-end max-phone:px-2.5 max-phone:py-1 max-phone:text-12"
      />
      <div className="flex flex-wrap items-baseline gap-3.5 max-phone:col-start-1 max-phone:row-span-2 max-phone:row-start-1 max-phone:flex-col max-phone:gap-0.5">
        <Eyebrow className="hidden max-phone:block">
          {night ? 'NIGHT' : 'DAY'} {roman(s.day)}
        </Eyebrow>
        <b className="font-serif text-20 max-phone:text-24 max-phone:font-black">
          {s.day ? `第 ${s.day} ${night ? '夜' : '天'} · ${phase}` : phase}
        </b>
        <span className="text-14 text-dim max-phone:text-13">
          {running && cur.seat ? (
            <>
              正在等 <em className="font-medium text-gold-hi not-italic">{cur.seat} 号</em>「
              {cur.action_cn || cur.action_type || ''}」
            </>
          ) : !running && s.winner_cn ? (
            `${s.winner_cn}胜利`
          ) : null}
        </span>
      </div>
      <span className="flex-1 max-phone:hidden" />
      <div className="flex items-center gap-3 max-phone:fixed max-phone:inset-x-0 max-phone:bottom-0 max-phone:z-15 max-phone:gap-2.5 max-phone:border-t max-phone:border-line max-phone:bg-night max-phone:px-4 max-phone:pt-3 max-phone:pb-[calc(14px+env(safe-area-inset-bottom))]">
        <label
          title={locked ? '有真人玩家的对局，结束前不能开上帝视角' : undefined}
          className={cn(
            'flex min-h-11 cursor-pointer items-center gap-2.5 rounded-full border border-gold-line bg-god-bg py-1.5 pr-2 pl-3.5 text-14 text-gold-hi max-phone:h-12 max-phone:flex-1 max-phone:justify-center max-phone:rounded-xl max-phone:bg-transparent',
            locked && 'cursor-not-allowed opacity-60',
          )}
        >
          <Icon name={locked ? 'lock' : 'eye'} />
          <span>{locked ? '上帝视角已锁' : '上帝视角'}</span>
          <Switch size="sm" checked={god} disabled={locked} onChange={onGodChange} />
        </label>
        <Button
          variant="danger"
          disabled={!running}
          onClick={onStop}
          className="max-phone:h-12 max-phone:w-24"
        >
          <Icon name="stop" />
          中止
        </Button>
      </div>
    </div>
  );
}
