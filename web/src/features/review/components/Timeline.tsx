import type { Replay } from '@/api/types';
import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';
import { stripGod } from '@/lib/format';

/** 战报时间线：一夜 / 一天一个节点 */
export function Timeline({ replay }: { replay: Replay }) {
  const rounds = (replay.timeline ?? []).filter((r) => (r.items ?? []).length);

  if (!rounds.length) {
    // 旧服务端没有结构化时间线：直接展示 Markdown 战报
    return (
      <pre className="m-0 rounded-[14px] border border-line bg-card p-5 text-13_5 leading-[1.7] break-words whitespace-pre-wrap">
        {replay.markdown || '（没有战报）'}
      </pre>
    );
  }

  return (
    <section aria-label="战报时间线" className="flex flex-col">
      {rounds.map((r, i) => {
        const night = r.kind === 'night';
        const last = i === rounds.length - 1;
        return (
          <div key={`${r.day}-${r.kind}`} className="flex gap-5 max-phone:gap-3">
            <div className="flex w-10 flex-none flex-col items-center max-phone:w-8">
              <span
                className={cn(
                  'flex size-9 items-center justify-center rounded-full border max-phone:size-8',
                  night ? 'border-line-strong bg-well text-vil-fg' : 'border-gold bg-notice text-gold-hi',
                )}
              >
                <Icon name={night ? 'moon' : 'sun'} className="size-4" />
              </span>
              {!last && <span className="min-h-4 w-px flex-1 bg-line" />}
            </div>
            <div className="flex min-w-0 flex-1 flex-col gap-1.5 pb-5">
              <h3
                className={cn(
                  'm-0 font-serif text-17 leading-9 font-bold max-phone:text-16 max-phone:leading-8',
                  night ? 'text-vil-fg' : 'text-gold-hi',
                )}
              >
                {r.title || `第 ${r.day} ${night ? '夜' : '天'}`}
              </h3>
              {(r.items ?? []).map((t, j) => (
                <p
                  key={j}
                  className="m-0 flex gap-2.5 text-14 leading-[1.7] text-vil-fg before:flex-none before:text-gold-line before:content-['◆'] max-phone:text-13_5"
                >
                  {stripGod(t)}
                </p>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
