import type { Snapshot } from '@/api/types';
import { Hint } from '@/components/ui/Card';
import { Eyebrow } from '@/components/ui/Eyebrow';
import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';
import { isNight, roman } from '@/lib/format';

/** 桌心：昼夜图标、阶段名、警长 / 存活人数、发言进度条 */
export function TableCenter({ snapshot: s }: { snapshot: Snapshot }) {
  const night = isNight(s.phase);
  const alive = s.players.filter((p) => p.alive).length;
  const sub = [
    s.sheriff ? `警长 ${s.sheriff} 号` : s.sheriff_status_cn || null,
    `存活 ${alive} / ${s.players.length}`,
  ].filter(Boolean);
  const sp = s.speech_progress;

  return (
    <div className="absolute top-[47%] left-1/2 flex w-[44%] -translate-1/2 flex-col items-center gap-2 text-center max-phone:gap-0.5">
      <span className="flex size-14 items-center justify-center rounded-full border border-gold bg-well text-gold-hi max-phone:size-auto max-phone:border-0 max-phone:bg-transparent">
        <Icon name={night ? 'moon' : 'sun'} className="size-7 max-phone:size-6" />
      </span>
      <Eyebrow className="max-phone:hidden">
        {night ? 'NIGHT' : 'DAY'} {roman(s.day)}
      </Eyebrow>
      <b className="font-serif text-[clamp(20px,2.4vw,30px)] leading-[1.2] font-black tracking-[2px] max-phone:text-16 max-phone:tracking-normal">
        {s.phase_cn || s.phase || ''}
      </b>
      <Hint className="max-phone:text-11">{sub.join(' · ')}</Hint>
      {/* 没有发言进度时也保留这一格，桌心文字的垂直位置才不会跳 */}
      <div
        role={sp?.total ? 'img' : undefined}
        aria-label={sp?.total ? `发言进度 ${sp.done} / ${sp.total}` : undefined}
        className="mt-1 flex flex-wrap justify-center gap-1 max-phone:hidden"
      >
        {Array.from({ length: sp?.total ?? 0 }, (_, i) => (
          <i
            key={i}
            className={cn(
              'h-1 w-[18px] rounded-[2px] bg-line',
              sp && i < sp.done && 'bg-gold',
              sp && i === sp.done && 'bg-gold-hi shadow-[0_0_8px_var(--color-gold)]',
            )}
          />
        ))}
      </div>
    </div>
  );
}
