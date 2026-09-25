import type { Replay } from '@/api/types';
import { fmtDuration } from '@/lib/format';

export function ResultStats({ replay }: { replay: Replay }) {
  const res = replay.result ?? {};
  const st = res.stats ?? {};
  const alive = st.n_alive ?? (res.alive ?? []).length;
  const stats = (
    [
      [st.days ?? res.days, '天'],
      [st.n_speeches, '条发言'],
      [alive, '人存活'],
      [fmtDuration(replay.duration_s), '用时'],
      [res.n_thoughts, '条心路历程'],
    ] as const
  )
    .filter(([v]) => v != null && v !== '')
    .slice(0, 4);

  return (
    <div className="mt-2 flex flex-wrap gap-7 text-14 text-dim max-phone:mt-3 max-phone:grid max-phone:w-full max-phone:grid-cols-4 max-phone:gap-0 max-phone:border-t max-phone:border-line max-phone:pt-3.5">
      {stats.map(([value, label]) => (
        <span key={label} className="max-phone:flex max-phone:flex-col max-phone:text-12">
          <b className="mr-1 font-serif text-22 text-fg max-phone:m-0 max-phone:text-20">{value}</b>
          {label}
        </span>
      ))}
    </div>
  );
}
