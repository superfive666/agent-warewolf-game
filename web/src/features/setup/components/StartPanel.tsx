import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';

interface StartPanelProps {
  starting: boolean;
  subtitle: string;
  onStart: () => void;
}

/** 「天黑请闭眼」。手机上固定在屏幕底部 */
export function StartPanel({ starting, subtitle, onStart }: StartPanelProps) {
  return (
    <div className="flex flex-col gap-2 max-phone:fixed max-phone:inset-x-0 max-phone:bottom-0 max-phone:z-15 max-phone:gap-1 max-phone:border-t max-phone:border-line max-phone:bg-night max-phone:px-4 max-phone:pt-3 max-phone:pb-[calc(14px+env(safe-area-inset-bottom))]">
      <Button variant="cta" disabled={starting} onClick={onStart}>
        <Icon name="moon" className="size-[22px]" />
        <span className="font-serif text-20 font-black tracking-[4px] max-phone:text-18 max-phone:tracking-[3px]">
          {starting ? '正在发牌…' : '天黑请闭眼'}
        </span>
      </Button>
      <p className="m-0 text-center text-13 text-dim max-phone:text-12">{subtitle}</p>
    </div>
  );
}
