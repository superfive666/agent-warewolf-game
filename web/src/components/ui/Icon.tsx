import { cn } from '@/lib/cn';

import { ICON_PATHS, type IconName } from './icons';

interface IconProps {
  name: IconName;
  className?: string;
  /** 不套默认的描边样式（例如实心星标、盾牌） */
  bare?: boolean;
}

export function Icon({ name, className, bare = false }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={cn(!bare && 'icon', className)}>
      {ICON_PATHS[name]}
    </svg>
  );
}
