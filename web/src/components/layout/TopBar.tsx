import { Icon } from '@/components/ui/Icon';
import { IconButton } from '@/components/ui/IconButton';
import type { View } from '@/lib/view';

import { Brand } from './Brand';
import { StepNav } from './StepNav';

interface TopBarProps {
  view: View;
  gameId: string | null;
  hasReplay: boolean;
  onNavigate: (v: View) => void;
  onOpenHistory: () => void;
}

export function TopBar({ view, gameId, hasReplay, onNavigate, onOpenHistory }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-[72px] items-center gap-8 border-b border-rule bg-night px-gutter max-phone:h-14 max-phone:gap-2.5">
      <Brand onClick={() => onNavigate('setup')} />
      <StepNav view={view} hasGame={!!gameId} hasReplay={hasReplay} onNavigate={onNavigate} />
      <span className="flex-1 max-phone:hidden" />
      {gameId && (
        <span className="font-mono text-13 text-faint max-laptop:hidden">game · {gameId.slice(0, 6)}</span>
      )}
      <IconButton aria-label="历史对局" onClick={onOpenHistory} className="max-phone:-mr-2">
        <Icon name="list" />
        <span className="max-tablet:hidden">历史对局</span>
      </IconButton>
    </header>
  );
}
