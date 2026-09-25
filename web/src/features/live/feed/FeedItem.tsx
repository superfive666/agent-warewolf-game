import { memo } from 'react';

import type { GameEvent } from '@/api/types';
import type { Side } from '@/components/ui/Avatar';
import { Icon } from '@/components/ui/Icon';
import { isNight, stripGod } from '@/lib/format';
import { parseDivider, speechBody, SPEECH_TYPES } from '@/lib/game';

import { ChannelNote } from './ChannelNote';
import { PhaseDivider } from './PhaseDivider';
import { SpeechMessage } from './SpeechMessage';
import { SystemNote } from './SystemNote';

interface FeedItemProps {
  event: GameEvent;
  /** 下面三个只对发言有用；拆成原始值是为了让 memo 生效 */
  side?: Side | undefined;
  agent?: string | undefined;
  roleCn?: string | undefined;
}

/** 把一条引擎事件渲染成实况里的一行 */
export const FeedItem = memo(function FeedItem({ event: e, side, agent, roleCn }: FeedItemProps) {
  const text = String(e.text ?? '');

  const divider = parseDivider(e);
  if (divider) {
    const rest = stripGod(divider.rest).trim();
    return (
      <>
        <PhaseDivider>
          {divider.title.replace(/\s+白天$/, '') + (isNight(e.phase) ? ' · 天黑请闭眼' : '')}
        </PhaseDivider>
        {rest && !/^天黑请闭眼。?$/.test(rest) && <SystemNote>{rest}</SystemNote>}
      </>
    );
  }

  if (e.actor && SPEECH_TYPES.has(e.type)) {
    const channel = e.audience === 'wolves' ? 'wolves' : e.audience === 'private' ? 'private' : 'public';
    return (
      <SpeechMessage
        seat={e.actor}
        channel={channel}
        body={speechBody(text)}
        side={side}
        agent={agent}
        roleCn={roleCn}
        wolfChat={e.type === 'wolf_chat'}
      />
    );
  }

  if (e.audience === 'wolves' || e.audience === 'private') {
    return (
      <ChannelNote
        channel={e.audience === 'wolves' ? 'wolves' : 'private'}
        phase={e.phase_cn ?? ''}
        text={stripGod(text)}
      />
    );
  }
  if (e.audience === 'god') {
    return (
      <SystemNote tone="god">
        <Icon name="eye" className="inline align-baseline" /> {stripGod(text)}
      </SystemNote>
    );
  }
  if (e.type === 'explode') return <SystemNote tone="explode">{text.replace(/^💥\s*/, '')}</SystemNote>;
  return <SystemNote>{stripGod(text)}</SystemNote>;
});
