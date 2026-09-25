import { cn } from '@/lib/cn';

const ITEMS = [
  { label: '行动中', dot: 'border-gold-hi', godOnly: false },
  { label: '警长', dot: 'border-gold bg-gold', godOnly: false },
  { label: '狼人', dot: 'border-wolf', godOnly: true },
  { label: '好人', dot: 'border-good', godOnly: true },
  { label: '已出局', dot: 'border-seat-dead opacity-60', godOnly: false },
];

export function TableLegend({ god }: { god: boolean }) {
  return (
    <div className="flex flex-wrap justify-center gap-[18px] text-12 text-dim max-phone:gap-2.5 max-phone:pb-1.5 max-phone:text-11">
      {ITEMS.filter((it) => god || !it.godOnly).map((it) => (
        <span key={it.label} className="flex items-center gap-1.5">
          <i className={cn('inline-block size-2.5 rounded-full border-2', it.dot)} />
          {it.label}
        </span>
      ))}
    </div>
  );
}
