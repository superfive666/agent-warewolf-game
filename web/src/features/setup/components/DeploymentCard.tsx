import type { Options } from '@/api/types';
import { Card, CardTitle } from '@/components/ui/Card';
import { splitDesc } from '@/lib/format';

import type { SetupState } from '../model';
import type { SetupAction } from '../useSetupForm';

import { DeploymentPicker } from './DeploymentPicker';
import { ModelAccess } from './ModelAccess';

interface DeploymentCardProps {
  options: Options;
  state: SetupState;
  dispatch: (a: SetupAction) => void;
}

export function DeploymentCard({ options, state, dispatch }: DeploymentCardProps) {
  const [, hint] = splitDesc(options.deployments[state.deployment] ?? '');
  return (
    <Card>
      <CardTitle>部署模式</CardTitle>
      <DeploymentPicker
        deployments={options.deployments}
        value={state.deployment}
        onChange={(value) => dispatch({ type: 'set', field: 'deployment', value })}
      />
      <p className="-mt-1.5 mb-0 text-13 text-dim">{hint}</p>
      <ModelAccess state={state} dispatch={dispatch} />
    </Card>
  );
}
