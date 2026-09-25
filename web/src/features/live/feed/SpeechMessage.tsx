import { Avatar, type Side } from '@/components/ui/Avatar';
import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';

export type SpeechChannel = 'public' | 'wolves' | 'private';

interface SpeechMessageProps {
  seat: number;
  channel: SpeechChannel;
  body: string;
  side?: Side | undefined;
  agent?: string | undefined;
  /** 只有上帝视角才显示真实身份 */
  roleCn?: string | undefined;
  wolfChat?: boolean;
}

const BUBBLE: Record<SpeechChannel, string> = {
  public: 'bg-raised',
  wolves: 'border border-wolfchat-line bg-wolfchat-bg',
  private: 'border border-priv-line bg-priv-bg',
};

export function SpeechMessage({ seat, channel, body, side, agent, roleCn, wolfChat }: SpeechMessageProps) {
  return (
    <div className="flex gap-3 max-phone:gap-2.5">
      <Avatar seat={seat} side={side} className="max-phone:size-8 max-phone:text-14" />
      <div className="flex min-w-0 flex-col gap-1">
        <span className="text-12 text-dim">
          {wolfChat && <Icon name="wolf" className="inline align-baseline" />}
          {seat} 号{agent ? ` · ${agent}` : ''}
          {roleCn && <em className="text-wolf-fg not-italic"> · {roleCn}</em>}
        </span>
        <div
          className={cn(
            'rounded-[4px_12px_12px_12px] px-3.5 py-2.5 wrap-anywhere whitespace-pre-wrap max-phone:px-3',
            BUBBLE[channel],
          )}
        >
          {body}
        </div>
      </div>
    </div>
  );
}
