import { useState } from 'react';

import type { Options } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { cn } from '@/lib/cn';
import { effortCn } from '@/lib/format';

import { backendModels, type SeatConfig } from '../model';

interface BulkApplyProps {
  options: Options;
  onApply: (seat: SeatConfig) => void;
}

const CONTROL = 'h-10 w-auto flex-[1_1_140px] max-phone:h-11 max-phone:flex-[1_1_40%]';

const firstModel = (options: Options, backend: string) =>
  Object.keys(backendModels(options, backend))[0] ?? '';

/** 「快速套用」：一次把所有座位设成同一个后端 / 模型 / 强度 */
export function BulkApply({ options, onApply }: BulkApplyProps) {
  const [backend, setBackend] = useState(() =>
    'claude' in options.backends ? 'claude' : (Object.keys(options.backends)[0] ?? 'heuristic'),
  );
  const [model, setModel] = useState(() => firstModel(options, backend));
  const [custom, setCustom] = useState('');
  const [effort, setEffort] = useState('medium');

  const info = options.backends[backend];
  const models = Object.entries(backendModels(options, backend));
  const effortDisabled = !models.length && !info?.custom_model;

  return (
    <div className="flex flex-wrap items-center gap-2.5 rounded-xl border border-dashed border-seat-dead bg-page px-4 py-3.5 max-phone:p-3.5">
      <span className="flex items-center gap-1.5 text-14 font-medium whitespace-nowrap text-gold max-phone:basis-full">
        <Icon name="bolt" />
        快速套用
      </span>
      <Select
        aria-label="后端"
        className={CONTROL}
        value={backend}
        options={Object.entries(options.backends).map(([k, v]) => [k, v.label] as const)}
        onChange={(v) => {
          setBackend(v);
          setModel(firstModel(options, v));
        }}
      />
      {models.length > 0 && (
        <Select
          aria-label="模型"
          className={CONTROL}
          value={model}
          options={models.map(([k, v]) => [k, v.label] as const)}
          onChange={setModel}
        />
      )}
      {info?.custom_model && (
        <Input
          aria-label="自定义模型名"
          className={CONTROL}
          placeholder="自定义模型名"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
        />
      )}
      <Select
        aria-label="思考强度"
        className={cn(CONTROL, 'flex-[0_0_110px]')}
        disabled={effortDisabled}
        value={effort}
        options={options.efforts.map((e) => [e, `思考 · ${effortCn(e)}`] as const)}
        onChange={setEffort}
      />
      <Button
        variant="outline"
        className="max-phone:flex-[1_1_100%]"
        onClick={() => onApply({ backend, model, custom: custom.trim(), effort })}
      >
        套用到全部座位
      </Button>
    </div>
  );
}
