import { Fragment } from 'react';

import { cn } from '@/lib/cn';
import type { View } from '@/lib/view';

interface Step {
  view: View;
  numeral: string;
  label: string;
  enabled: boolean;
}

interface StepNavProps {
  view: View;
  hasGame: boolean;
  hasReplay: boolean;
  onNavigate: (v: View) => void;
}

/** 顶栏里的 I · II · III 三步 */
export function StepNav({ view, hasGame, hasReplay, onNavigate }: StepNavProps) {
  const steps: Step[] = [
    { view: 'setup', numeral: 'I', label: '配置牌局', enabled: true },
    { view: 'live', numeral: 'II', label: '对局', enabled: hasGame },
    { view: 'review', numeral: 'III', label: '复盘', enabled: hasReplay },
  ];
  return (
    <nav aria-label="流程" className="flex items-center gap-2 max-phone:ml-auto max-phone:gap-1">
      {steps.map((s, i) => (
        <Fragment key={s.view}>
          {i > 0 && (
            <span
              aria-hidden="true"
              className={cn(
                'h-px w-7 bg-line-strong max-phone:w-2',
                (i === 1 ? hasGame : hasReplay) && 'bg-gold',
              )}
            />
          )}
          <button
            type="button"
            disabled={!s.enabled}
            aria-current={view === s.view ? 'step' : undefined}
            onClick={() => onNavigate(s.view)}
            className={cn(
              'flex items-center gap-2.5 rounded-full border border-line bg-transparent px-4 py-2 text-14 text-dim',
              'disabled:cursor-default disabled:opacity-45 max-laptop:px-3',
              'max-phone:size-[30px] max-phone:justify-center max-phone:gap-0 max-phone:p-0 max-phone:text-[0px]',
              view === s.view && 'border-gold bg-raised font-medium text-gold-hi',
            )}
          >
            <i className="font-latin font-bold not-italic max-phone:text-12">{s.numeral}</i>
            {s.label}
          </button>
        </Fragment>
      ))}
    </nav>
  );
}
