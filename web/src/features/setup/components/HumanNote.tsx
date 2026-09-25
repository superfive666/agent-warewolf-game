import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';

/** 选了真人座位时的提示；选了不止一个时标红（开局会被拒） */
export function HumanNote({ seats }: { seats: number[] }) {
  const error = seats.length > 1;
  return (
    <div
      className={cn(
        'flex gap-3 rounded-xl border border-gold-line bg-notice px-4 py-3.5 text-13 leading-[1.6] text-notice-fg',
        error && 'border-wolf-line bg-wolf-bg text-wolf-soft',
      )}
    >
      <Icon name={error ? 'warn' : 'eye'} className="mt-0.5" />
      {error ? (
        <b className="font-medium text-wolf-fg">
          一桌只能有 1 个真人座位，现在选了 {seats.map((s) => `${s} 号`).join('、')} —— 开局会被拒绝。
        </b>
      ) : (
        <span>
          你坐 {seats[0]} 号位，其余座位由 agent 来坐。轮到你时页面上方会出现操作面板；
          有真人在打的对局，结束前不能开上帝视角。
        </span>
      )}
    </div>
  );
}
