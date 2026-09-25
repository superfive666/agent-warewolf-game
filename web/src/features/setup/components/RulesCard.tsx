import type { WinRule } from '@/api/types';
import { Card, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input } from '@/components/ui/Input';
import { Segmented } from '@/components/ui/Segmented';

import type { SetupState } from '../model';
import type { SetupAction } from '../useSetupForm';

import { SwitchRow } from './SwitchRow';

const WIN_RULES = [
  ['edge', '屠边'],
  ['city', '屠城'],
] as const satisfies readonly (readonly [WinRule, string])[];

interface RulesCardProps {
  state: SetupState;
  dispatch: (a: SetupAction) => void;
}

export function RulesCard({ state, dispatch }: RulesCardProps) {
  return (
    <Card>
      <CardTitle>规则</CardTitle>
      <div className="flex flex-col gap-1.5">
        <span className="text-13 text-dim">胜负规则</span>
        <Segmented
          label="胜负规则"
          value={state.winRule}
          options={WIN_RULES}
          onChange={(value) => dispatch({ type: 'set', field: 'winRule', value })}
        />
      </div>
      <div className="flex flex-col">
        <SwitchRow
          title="警长竞选"
          description="上警 · 警上发言 · 退水 · 警徽流"
          checked={state.sheriff}
          onChange={(value) => dispatch({ type: 'set', field: 'sheriff', value })}
        />
        <SwitchRow
          title="允许狼人自爆"
          description="自爆后跳过投票直接入夜"
          checked={state.explode}
          onChange={(value) => dispatch({ type: 'set', field: 'explode', value })}
        />
      </div>
      <div className="grid grid-cols-2 gap-3.5 max-phone:gap-3">
        <Field label="发言字数上限" help="450 字 ≈ 真人讲 2 分钟">
          <Input
            type="number"
            min={50}
            max={2000}
            value={state.maxSpeech}
            onChange={(e) => dispatch({ type: 'set', field: 'maxSpeech', value: e.target.value })}
          />
        </Field>
        <Field label="最大迭代次数" help="每个决策点最多问几次">
          <Input
            type="number"
            min={1}
            max={10}
            value={state.maxIter}
            onChange={(e) => dispatch({ type: 'set', field: 'maxIter', value: e.target.value })}
          />
        </Field>
        <Field label="随机种子" className="col-span-2">
          <Input
            type="number"
            placeholder="留空 = 每局都不同"
            value={state.seed}
            onChange={(e) => dispatch({ type: 'set', field: 'seed', value: e.target.value })}
          />
        </Field>
      </div>
    </Card>
  );
}
