import type { Thought } from '@/api/types';
import { cn } from '@/lib/cn';

/** 一个决策点的内心想法 + 实际动作；被打回的尝试会标红 */
export function ThoughtEntry({ thought: t }: { thought: Thought }) {
  return (
    <div className="flex flex-col gap-1.5 pt-3.5">
      <div className="flex items-center gap-2 text-12 text-gold after:order-1 after:h-px after:flex-1 after:bg-rule after:content-['']">
        第{t.day}天 · {t.phase_cn || t.phase} · {t.action_cn || t.action_type}
        {!t.accepted && (
          <span className="order-2 rounded-full border border-wolf-line px-2 py-px text-11 text-wolf-fg">
            第 {t.attempt} 次被打回
          </span>
        )}
      </div>
      <p
        className={cn(
          'm-0 font-serif text-14_5 leading-[1.85] wrap-anywhere whitespace-pre-wrap max-phone:text-14',
          !t.accepted && 'text-dim',
        )}
      >
        {t.thought}
      </p>
      {!t.accepted && t.error && <span className="text-12 text-wolf-fg">被判非法：{t.error}</span>}
      {t.action_desc && (
        <span className="self-start rounded-md bg-inset px-2.5 py-[3px] font-mono text-12 text-dim">
          → {t.action_desc}
        </span>
      )}
    </div>
  );
}
