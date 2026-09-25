import type { ViewEvent } from '@/api/types';
import { Eyebrow } from '@/components/ui/Eyebrow';

/** 只有你能看到的消息：狼人频道、验人结果、用药结果…… */
export function PrivateLog({ events }: { events: ViewEvent[] }) {
  if (!events.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <Eyebrow>只有你知道</Eyebrow>
      <ul className="m-0 flex max-h-56 list-none flex-col gap-1.5 overflow-y-auto p-0 text-13 leading-[1.6]">
        {events.map((e) => (
          <li
            key={e.seq}
            className="rounded-lg border border-priv-line bg-priv-bg px-3 py-2 wrap-anywhere text-priv-soft"
          >
            <span className="mr-2 text-12 text-priv-fg">{e.phase_cn}</span>
            {e.text}
          </li>
        ))}
      </ul>
    </div>
  );
}
