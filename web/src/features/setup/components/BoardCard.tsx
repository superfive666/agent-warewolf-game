import type { Options, WinRule } from '@/api/types';
import { Card, CardHead } from '@/components/ui/Card';

import { BoardPicker } from './BoardPicker';
import { BoardRoles } from './BoardRoles';

interface BoardCardProps {
  options: Options;
  nPlayers: number;
  winRule: WinRule;
  onChange: (n: number) => void;
}

export function BoardCard({ options, nPlayers, winRule, onChange }: BoardCardProps) {
  const board = options.boards[String(nPlayers)];
  return (
    <Card>
      <CardHead
        title="选择板子"
        hint={
          winRule === 'city' ? '胜负规则：屠城（狼人要杀光所有好人）' : '胜负规则：屠边（杀光神职或平民即胜）'
        }
      />
      <BoardPicker boards={options.boards} value={nPlayers} onChange={onChange} />
      {board && <BoardRoles board={board} />}
    </Card>
  );
}
