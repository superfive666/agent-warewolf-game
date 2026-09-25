import { Avatar } from '@/components/ui/Avatar';

/** 「3 号正在想『发言』…」 */
export function ThinkingBubble({ seat, action }: { seat: number; action: string }) {
  return (
    <div className="flex items-center gap-3 max-phone:gap-2.5">
      <Avatar
        seat={seat}
        className="border-gold-hi text-gold-hi shadow-[0_0_12px_rgba(240,212,138,.4)] max-phone:size-8 max-phone:text-14"
      />
      <span className="flex items-center gap-1.5 rounded-[4px_12px_12px_12px] bg-raised px-4 py-2.5 text-dim">
        {seat} 号正在想「{action}」
        <span className="inline-flex gap-1" aria-hidden="true">
          <i className="size-[5px] animate-blink rounded-full bg-gold" />
          <i className="size-[5px] animate-blink rounded-full bg-gold [animation-delay:.2s]" />
          <i className="size-[5px] animate-blink rounded-full bg-gold [animation-delay:.4s]" />
        </span>
      </span>
    </div>
  );
}
