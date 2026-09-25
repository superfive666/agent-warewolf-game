import { Icon } from '@/components/ui/Icon';

export function Brand({ onClick }: { onClick: () => void }) {
  return (
    <a
      href="#/"
      onClick={(e) => {
        e.preventDefault();
        onClick();
      }}
      className="flex items-center gap-3 text-fg no-underline"
    >
      <span className="flex size-10 items-center justify-center rounded-full border border-gold text-gold max-phone:size-8">
        <Icon name="moon" className="size-5 max-phone:size-4" />
      </span>
      <span className="flex flex-col leading-[1.15]">
        <b className="font-serif text-19 tracking-[3px] text-gold-hi max-phone:text-17">狼人杀</b>
        <small className="font-latin text-11 tracking-[2.5px] text-dim max-phone:hidden">AGENT SANDBOX</small>
      </span>
    </a>
  );
}
