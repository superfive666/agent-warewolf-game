import type { ReactNode } from 'react';

import type { GameResult } from '@/api/types';
import { Accordion } from '@/components/ui/Accordion';
import { Avatar } from '@/components/ui/Avatar';
import { seatSide } from '@/lib/game';

interface SeatAccordionProps {
  seat: number;
  result: GameResult;
  title: string;
  subtitle: string;
  defaultOpen?: boolean;
  children: ReactNode;
}

export function SeatAccordion({ seat, result, title, subtitle, defaultOpen, children }: SeatAccordionProps) {
  return (
    <Accordion
      // 这里的头像字号跟随正文（手机上 14px），和实况里的头像不同
      leading={<Avatar seat={seat} side={seatSide(result, seat)} className="max-phone:text-14" />}
      title={title}
      subtitle={subtitle}
      defaultOpen={defaultOpen}
    >
      {children}
    </Accordion>
  );
}
