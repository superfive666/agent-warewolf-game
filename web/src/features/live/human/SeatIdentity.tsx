import type { SeatIdentity as Identity } from '@/api/types';
import { Eyebrow } from '@/components/ui/Eyebrow';

interface SeatIdentityProps {
  identity: Identity;
  knowledge: string[];
}

/** 你的底牌：座位、身份、阵营目标和只有你知道的信息 */
export function SeatIdentity({ identity: me, knowledge }: SeatIdentityProps) {
  return (
    <div className="flex flex-col gap-2">
      <Eyebrow>你的底牌</Eyebrow>
      <b className="font-serif text-24 text-gold-hi max-phone:text-20">
        {me.seat} 号 · {me.role_cn}
        <span className="ml-2 text-14 font-normal text-dim">
          {me.faction_cn}
          {me.is_sheriff && ' · 警长'}
          {!me.alive && ' · 已出局'}
        </span>
      </b>
      <p className="m-0 text-13 leading-[1.6] text-dim">{me.role_brief}</p>
      <p className="m-0 text-13 leading-[1.6] text-dim">目标：{me.win_condition}</p>
      {knowledge.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-13 text-fg">
          {knowledge.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
