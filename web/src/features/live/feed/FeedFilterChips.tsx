import { Chip, type ChipTone } from '@/components/ui/Chip';
import type { FeedFilter } from '@/lib/game';

const FILTERS: { key: FeedFilter; label: string; tone?: ChipTone; godOnly?: boolean }[] = [
  { key: 'all', label: '全部' },
  { key: 'speech', label: '公开发言' },
  { key: 'wolves', label: '狼人频道', tone: 'wolves', godOnly: true },
  { key: 'private', label: '私聊', tone: 'private', godOnly: true },
  { key: 'system', label: '系统' },
];

interface FeedFilterChipsProps {
  value: FeedFilter;
  god: boolean;
  onChange: (f: FeedFilter) => void;
}

export function FeedFilterChips({ value, god, onChange }: FeedFilterChipsProps) {
  return (
    <div role="group" aria-label="频道筛选" className="no-scrollbar flex gap-1.5 overflow-x-auto">
      {FILTERS.map((f) => {
        const locked = !!f.godOnly && !god;
        return (
          <Chip
            key={f.key}
            tone={f.tone}
            lockable={f.godOnly}
            active={value === f.key}
            disabled={locked}
            title={locked ? '开启上帝视角后可看' : undefined}
            onClick={() => onChange(f.key)}
          >
            {f.label}
          </Chip>
        );
      })}
    </div>
  );
}
