import { useId, useState } from 'react';

import type { Options } from '@/api/types';
import { Icon } from '@/components/ui/Icon';
import { Input } from '@/components/ui/Input';
import { Medal } from '@/components/ui/Medal';
import { Select } from '@/components/ui/Select';
import { cn } from '@/lib/cn';

import { backendModels, hasModelChoice, seatSummary, type SeatConfig } from '../model';

import { BackendTag } from './BackendTag';
import { EffortPicker } from './EffortPicker';

interface SeatCardProps {
  index: number;
  seat: SeatConfig;
  options: Options;
  onChange: (patch: Partial<SeatConfig>) => void;
}

const CONTROL = 'h-[38px] text-13 max-phone:h-11 max-phone:text-14';

/** 一个座位的配置。桌面上常驻展开；手机上折叠成一行，点开编辑 */
export function SeatCard({ index, seat, options, onChange }: SeatCardProps) {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const no = index + 1;
  const backend = options.backends[seat.backend];
  const models = backendModels(options, seat.backend);
  const modelKeys = Object.keys(models);
  const withModel = hasModelChoice(options, seat.backend);

  return (
    <div
      className={cn(
        'flex flex-col gap-2.5 rounded-xl border border-line bg-page p-3.5',
        'max-phone:gap-0 max-phone:rounded-none max-phone:border-0 max-phone:border-b max-phone:border-line-soft max-phone:bg-transparent max-phone:px-3.5 max-phone:py-0 max-phone:last:border-b-0',
        open && 'max-phone:bg-page max-phone:shadow-[inset_0_0_0_1px_var(--color-gold)]',
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={bodyId}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full cursor-default items-center gap-2.5 border-none bg-transparent p-0 text-left text-fg max-phone:min-h-15 max-phone:cursor-pointer"
      >
        <Medal>{String(no).padStart(2, '0')}</Medal>
        <span className="flex min-w-0 flex-1 flex-col">
          <b className="text-14 font-medium">{no} 号位</b>
          <small className="hidden truncate text-12 text-dim max-phone:block">
            {seatSummary(seat, options)}
          </small>
        </span>
        <BackendTag backend={seat.backend} label={backend?.label ?? seat.backend} />
        <Icon
          name="chev"
          className={cn(
            'hidden size-4 text-faint transition-transform max-phone:block',
            open && 'rotate-180 text-gold-hi',
          )}
        />
      </button>

      <div
        id={bodyId}
        className={cn(
          'flex flex-col gap-2',
          'max-phone:hidden',
          open && 'max-phone:flex max-phone:gap-2.5 max-phone:pb-3.5',
        )}
      >
        <Select
          aria-label={`${no} 号位后端`}
          className={CONTROL}
          value={seat.backend}
          options={Object.entries(options.backends).map(([k, v]) => [k, v.label] as const)}
          onChange={(v) => onChange({ backend: v, custom: '' })}
        />
        {modelKeys.length > 0 && (
          <Select
            aria-label={`${no} 号位模型`}
            className={CONTROL}
            value={seat.model}
            title={models[seat.model]?.note ?? ''}
            options={modelKeys.map((k) => [k, models[k]?.label ?? k] as const)}
            onChange={(v) => onChange({ model: v })}
          />
        )}
        {backend?.custom_model && (
          // 自建网关可以服务任意模型名，所以 openai 后端多给一个自由输入框
          <Input
            aria-label={`${no} 号位自定义模型名`}
            className={CONTROL}
            placeholder="自定义模型名（可选）"
            value={seat.custom}
            onChange={(e) => onChange({ custom: e.target.value.trim() })}
          />
        )}
        <EffortPicker
          label={`${no} 号位思考强度`}
          efforts={options.efforts}
          value={seat.effort}
          disabled={!withModel}
          onChange={(effort) => onChange({ effort })}
        />
      </div>
    </div>
  );
}
