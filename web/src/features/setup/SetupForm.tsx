import { useState } from 'react';

import { api } from '@/api/games';
import type { Options } from '@/api/types';
import { useToast } from '@/components/toast/useToast';
import { saveSeatToken } from '@/lib/seatToken';

import { BoardCard } from './components/BoardCard';
import { DeploymentCard } from './components/DeploymentCard';
import { HumanNote } from './components/HumanNote';
import { LineupCard } from './components/LineupCard';
import { LlmWarning } from './components/LlmWarning';
import { RulesCard } from './components/RulesCard';
import { StartPanel } from './components/StartPanel';
import { buildGameRequest, ctaSubtitle, humanSeats, llmUsage } from './model';
import { useSetupForm } from './useSetupForm';

interface SetupFormProps {
  options: Options;
  onStarted: (gameId: string) => void;
}

export function SetupForm({ options, onStarted }: SetupFormProps) {
  const [state, dispatch] = useSetupForm(options);
  const [starting, setStarting] = useState(false);
  const toast = useToast();
  const usage = llmUsage(state, options);
  const humans = humanSeats(state.seats);

  async function start() {
    setStarting(true);
    try {
      const game = await api.createGame(buildGameRequest(state));
      // 座位凭证只在开局返回里给这一次
      if (game.human) saveSeatToken(game.id, game.human.token);
      onStarted(game.id);
    } catch (e) {
      toast(`开局失败：${e instanceof Error ? e.message : String(e)}`, 8000);
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-[1560px] grid-cols-[minmax(0,1fr)_400px] items-start gap-8 px-gutter pt-10 pb-16 max-laptop:grid-cols-[minmax(0,1fr)_360px] max-laptop:gap-6 max-tablet:grid-cols-1 max-phone:gap-5 max-phone:px-4 max-phone:pt-5 max-phone:pb-[132px]">
      <div className="flex flex-col gap-6 max-phone:gap-5">
        <BoardCard
          options={options}
          nPlayers={state.nPlayers}
          winRule={state.winRule}
          onChange={(n) => dispatch({ type: 'setPlayers', n, options })}
        />
        <LineupCard
          options={options}
          seats={state.seats}
          onSeatChange={(index, patch) => dispatch({ type: 'updateSeat', index, patch, options })}
          onApplyAll={(seat) => dispatch({ type: 'applyAll', seat, options })}
        />
      </div>

      <aside className="sticky top-24 flex flex-col gap-6 max-tablet:static max-phone:gap-5">
        <RulesCard state={state} dispatch={dispatch} />
        <DeploymentCard options={options} state={state} dispatch={dispatch} />
        {humans.length > 0 && <HumanNote seats={humans} />}
        {usage && <LlmWarning usage={usage} />}
        <StartPanel starting={starting} subtitle={ctaSubtitle(state, options)} onStart={start} />
      </aside>
    </div>
  );
}
