import type { ReactNode } from 'react';

import { Icon } from './Icon';

interface AccordionProps {
  leading?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}

/** 复盘里按座位折叠的大块（心路历程 / 会话存档） */
export function Accordion({ leading, title, subtitle, defaultOpen = false, children }: AccordionProps) {
  return (
    <details
      open={defaultOpen}
      className="group mb-2.5 overflow-hidden rounded-[14px] border border-line bg-card open:border-gold max-phone:rounded-xl"
    >
      <summary className="no-marker flex min-h-15 cursor-pointer items-center gap-3 px-4 py-2 max-phone:px-3.5">
        {leading}
        <span className="flex min-w-0 flex-1 flex-col">
          <b className="font-medium">{title}</b>
          {subtitle != null && <small className="truncate text-12 text-dim">{subtitle}</small>}
        </span>
        <Icon
          name="chev"
          className="text-faint transition-transform group-open:rotate-180 group-open:text-gold-hi"
        />
      </summary>
      <div className="flex flex-col gap-[18px] border-t border-rule px-4 pt-1 pb-[18px] max-phone:px-3.5 max-phone:pb-4">
        {children}
      </div>
    </details>
  );
}
