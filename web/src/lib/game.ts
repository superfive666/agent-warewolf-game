import type { GameEvent, GameResult, RevealPlayer, SnapshotPlayer } from '@/api/types';

/** 这些事件都是某个座位在「说话」，渲染成气泡 */
export const SPEECH_TYPES = new Set([
  'speech',
  'sheriff_speech',
  'sheriff_pk_speech',
  'pk_speech',
  'last_words',
  'wolf_chat',
]);

export type FeedFilter = 'all' | 'speech' | 'wolves' | 'private' | 'system';

/** 事件属于哪个频道（决定筛选与配色） */
export function eventKind(e: GameEvent): Exclude<FeedFilter, 'all'> {
  if (e.audience === 'wolves') return 'wolves';
  if (e.audience === 'private') return 'private';
  if (e.actor && SPEECH_TYPES.has(e.type)) return 'speech';
  return 'system';
}

export const passesFilter = (e: GameEvent, f: FeedFilter): boolean => f === 'all' || eventKind(e) === f;

/** 「—— 第 1 夜 —— 天黑请闭眼」这种分隔线 → { title, rest }；不是分隔线返回 null */
export function parseDivider(e: GameEvent): { title: string; rest: string } | null {
  if (e.type !== 'phase' && e.type !== 'daybreak') return null;
  const m = String(e.text ?? '').match(/^——\s*(.+?)\s*——\s*(.*)$/s);
  if (!m) return null;
  return { title: m[1] ?? '', rest: m[2] ?? '' };
}

/** 发言正文：去掉「[警上发言] 3号：」这种前缀 */
export const speechBody = (text: string | undefined): string =>
  String(text ?? '')
    .replace(/^\[[^\]]+\]\s*/, '')
    .replace(/^[^：]{1,12}：/, '');

export const isWolfRole = (
  p: { role?: string | null; role_cn?: string | null } | null | undefined,
): boolean => !!p && (p.role === 'WEREWOLF' || p.role_cn === '狼人');

export type RoleTone = 'wolf' | 'god' | 'vil';

export const ROLE_NAME: Record<string, string> = {
  WEREWOLF: '狼人',
  SEER: '预言家',
  WITCH: '女巫',
  HUNTER: '猎人',
  IDIOT: '白痴',
  VILLAGER: '平民',
};

export function roleToneOf(role: string): RoleTone {
  if (role === 'WEREWOLF') return 'wolf';
  if (role === 'VILLAGER') return 'vil';
  return 'god';
}

export function revealTone(p: RevealPlayer): RoleTone {
  if (p.side === 'wolf' || p.role === 'WEREWOLF') return 'wolf';
  return p.role === 'VILLAGER' || p.role_cn === '平民' ? 'vil' : 'god';
}

/** 板子里的角色排序：狼人在前，平民在后，神职居中 */
export function sortBoardRoles(roles: Record<string, number>): [string, number][] {
  const rank = (r: string) => (r === 'WEREWOLF' ? 0 : r === 'VILLAGER' ? 2 : 1);
  return Object.entries(roles).sort(([a], [b]) => rank(a) - rank(b));
}

/** 圆桌座位下方那行小字：死因 / 真实身份 / 自称身份 */
export function seatRoleLine(p: SnapshotPlayer): { text: string; claimed: boolean } {
  if (!p.alive) {
    const nightDeath = p.died_cause === 'killed' || p.died_cause === 'poisoned';
    const when = p.died_day ? `第${p.died_day}${nightDeath ? '夜' : '天'} ` : '';
    return { text: when + (p.died_cause_cn || '出局'), claimed: false };
  }
  if (p.role_cn) {
    const claim = p.claim_cn && p.claim_cn !== p.role_cn ? ` · 自称${p.claim_cn}` : '';
    return { text: p.role_cn + claim, claimed: false };
  }
  if (p.revealed_role_cn) return { text: `${p.revealed_role_cn}（已翻牌）`, claimed: true };
  if (p.claim) return { text: `自称${p.claim_cn || p.claim}`, claimed: true };
  return { text: '', claimed: false };
}

/** 身份揭晓表。新服务端直接给 players；旧版 result 只有 roles_cn + lineup，就自己拼 */
export function revealRows(res: GameResult): RevealPlayer[] {
  if (Array.isArray(res.players) && res.players.length) return res.players;
  const alive = new Set(res.alive ?? []);
  const lineup = res.lineup ?? [];
  const roles = res.roles ?? {};
  const rolesCn = res.roles_cn ?? {};
  return Object.keys(rolesCn)
    .map(Number)
    .sort((a, b) => a - b)
    .map((seat) => {
      const death = (res.death_record ?? []).find((x) => x.seat === seat);
      const spec = lineup.find((x) => x.seat === seat);
      const role = roles[String(seat)];
      const isAlive = alive.has(seat);
      const isSheriff = res.sheriff === seat;
      return {
        seat,
        role,
        role_cn: rolesCn[String(seat)],
        side: role === 'WEREWOLF' ? 'wolf' : 'good',
        agent: spec?.label || spec?.model || spec?.backend || '',
        alive: isAlive,
        is_sheriff: isSheriff,
        fate_cn: isAlive
          ? isSheriff
            ? '存活 · 警长'
            : '存活'
          : death?.day
            ? `第${death.day}天出局`
            : '出局',
      };
    });
}

export function agentLabel(res: GameResult, seat: number): string {
  const spec = (res.lineup ?? []).find((x) => x.seat === seat);
  return spec ? spec.label || spec.model || spec.backend || '' : '';
}

/** 复盘里头像的阵营色：只有结束后 roles 里才有真实身份 */
export function seatSide(res: GameResult, seat: number): 'wolf' | 'good' | undefined {
  const role = res.roles?.[String(seat)];
  if (!role) return undefined;
  return role === 'WEREWOLF' ? 'wolf' : 'good';
}
