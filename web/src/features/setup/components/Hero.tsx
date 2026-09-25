import { Eyebrow } from '@/components/ui/Eyebrow';

import { HeroArt } from './HeroArt';

export function Hero() {
  return (
    <div className="relative h-[260px] overflow-hidden bg-hero px-gutter pt-14 max-phone:h-[168px] max-phone:px-4 max-phone:pt-6">
      <HeroArt />
      <div className="relative flex max-w-[760px] flex-col gap-3">
        <Eyebrow>CHAPTER I · THE GATHERING</Eyebrow>
        <h1 className="text-44 font-black tracking-[2px] max-phone:text-25 max-phone:tracking-[1px]">
          月升之前，先把这桌人请齐
        </h1>
        <p className="m-0 text-16 leading-[1.7] text-dim max-phone:max-w-[260px] max-phone:text-13">
          选人数，给每个座位挑后端与模型 → 开局后全自动跑完 → 出一份含每个 agent 心路历程的详细复盘。
        </p>
      </div>
    </div>
  );
}
