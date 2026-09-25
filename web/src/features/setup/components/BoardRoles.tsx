import type { BoardInfo } from '@/api/types';
import { Hint } from '@/components/ui/Card';
import { RolePill } from '@/components/ui/RolePill';
import { ROLE_NAME, roleToneOf, sortBoardRoles } from '@/lib/game';

export function BoardRoles({ board }: { board: BoardInfo }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Hint>{board.name.split('：')[0]}</Hint>
      {sortBoardRoles(board.roles ?? {}).map(([role, count]) => (
        <RolePill key={role} tone={roleToneOf(role)}>
          {(ROLE_NAME[role] ?? role) + (count > 1 ? ` ×${count}` : '')}
        </RolePill>
      ))}
    </div>
  );
}
