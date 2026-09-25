import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';

interface ChannelNoteProps {
  channel: 'wolves' | 'private';
  phase: string;
  text: string;
}

/** 狼人频道 / 私聊里的非发言消息（刀人结果、验人结果……） */
export function ChannelNote({ channel, phase, text }: ChannelNoteProps) {
  const wolves = channel === 'wolves';
  const accent = wolves ? 'text-wolf-fg' : 'text-priv-fg';
  return (
    <div
      className={cn(
        'flex gap-2.5 rounded-[10px] border px-3 py-2.5 wrap-anywhere',
        wolves
          ? 'border-wolfchat-line bg-wolfchat-bg text-wolfchat-fg'
          : 'border-priv-line bg-priv-bg text-priv-soft',
      )}
    >
      <Icon name={wolves ? 'wolf' : 'lock'} className={cn('mt-[3px] size-4', accent)} />
      <span>
        <b className={cn('mr-2 font-medium', accent)}>
          {wolves ? '狼人频道' : '私聊'} · {phase}
        </b>
        {text}
      </span>
    </div>
  );
}
