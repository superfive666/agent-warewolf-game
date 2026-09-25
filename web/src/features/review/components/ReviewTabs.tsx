import { useRef, type KeyboardEvent } from 'react';

import { cn } from '@/lib/cn';

export interface TabDef<K extends string> {
  key: K;
  label: string;
}

interface ReviewTabsProps<K extends string> {
  tabs: readonly TabDef<K>[];
  value: K;
  onChange: (key: K) => void;
  idPrefix: string;
}

/** WAI-ARIA tabs：左右方向键切换，Home / End 跳到首尾 */
export function ReviewTabs<K extends string>({ tabs, value, onChange, idPrefix }: ReviewTabsProps<K>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(e: KeyboardEvent) {
    const i = tabs.findIndex((t) => t.key === value);
    const next =
      e.key === 'ArrowRight'
        ? i + 1
        : e.key === 'ArrowLeft'
          ? i - 1
          : e.key === 'Home'
            ? 0
            : e.key === 'End'
              ? -1
              : null;
    if (next == null) return;
    e.preventDefault();
    const idx = (next + tabs.length) % tabs.length;
    const tab = tabs[idx];
    if (!tab) return;
    onChange(tab.key);
    refs.current[idx]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label="复盘内容"
      onKeyDown={onKeyDown}
      className="sticky top-[72px] z-10 no-scrollbar flex gap-2 overflow-x-auto border-b border-rule bg-page px-gutter max-phone:top-14 max-phone:grid max-phone:grid-cols-4 max-phone:gap-0 max-phone:p-0"
    >
      {tabs.map((t, i) => {
        const selected = t.key === value;
        return (
          <button
            key={t.key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${t.key}`}
            aria-controls={`${idPrefix}-panel-${t.key}`}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.key)}
            className={cn(
              'h-14 border-0 border-b-2 border-transparent bg-transparent px-5 text-15 whitespace-nowrap text-dim',
              'max-phone:h-[50px] max-phone:p-0 max-phone:text-14',
              selected && 'border-gold font-medium text-gold-hi',
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
