import { describe, expect, it } from 'vitest';

import type { GameEvent, SnapshotPlayer } from '@/api/types';

import { eventKind, parseDivider, revealRows, seatRoleLine, sortBoardRoles, speechBody } from '../game';

const ev = (e: Partial<GameEvent>): GameEvent => ({ type: 'system', ...e });
const player = (p: Partial<SnapshotPlayer>): SnapshotPlayer => ({
  seat: 1,
  alive: true,
  is_sheriff: false,
  ...p,
});

describe('eventKind', () => {
  it('按频道分类', () => {
    expect(eventKind(ev({ audience: 'wolves', type: 'wolf_chat', actor: 2 }))).toBe('wolves');
    expect(eventKind(ev({ audience: 'private' }))).toBe('private');
    expect(eventKind(ev({ type: 'speech', actor: 3, audience: 'public' }))).toBe('speech');
    expect(eventKind(ev({ type: 'speech' }))).toBe('system'); // 没有发言人
    expect(eventKind(ev({ type: 'vote', actor: 3 }))).toBe('system');
  });
});

describe('parseDivider', () => {
  it('识别阶段分隔线', () => {
    expect(parseDivider(ev({ type: 'phase', text: '—— 第 1 夜 —— 天黑请闭眼' }))).toEqual({
      title: '第 1 夜',
      rest: '天黑请闭眼',
    });
    expect(parseDivider(ev({ type: 'speech', text: '—— 第 1 夜 ——' }))).toBeNull();
    expect(parseDivider(ev({ type: 'phase', text: '普通文本' }))).toBeNull();
  });
});

it('speechBody 去掉前缀', () => {
  expect(speechBody('[警上发言] 3号：我是预言家')).toBe('我是预言家');
  expect(speechBody('3号：过')).toBe('过');
  expect(speechBody('没有前缀')).toBe('没有前缀');
});

describe('seatRoleLine', () => {
  it('死亡信息', () => {
    expect(
      seatRoleLine(player({ alive: false, died_day: 2, died_cause: 'killed', died_cause_cn: '被刀' })),
    ).toEqual({ text: '第2夜 被刀', claimed: false });
    expect(
      seatRoleLine(player({ alive: false, died_day: 2, died_cause: 'exiled', died_cause_cn: '放逐' })).text,
    ).toBe('第2天 放逐');
  });

  it('真实身份 / 自称', () => {
    expect(seatRoleLine(player({ role_cn: '狼人', claim_cn: '预言家' })).text).toBe('狼人 · 自称预言家');
    expect(seatRoleLine(player({ claim: 'SEER', claim_cn: '预言家' }))).toEqual({
      text: '自称预言家',
      claimed: true,
    });
    expect(seatRoleLine(player({ revealed_role_cn: '白痴' }))).toEqual({
      text: '白痴（已翻牌）',
      claimed: true,
    });
  });
});

it('sortBoardRoles 狼人在前、平民在后', () => {
  expect(sortBoardRoles({ VILLAGER: 4, SEER: 1, WEREWOLF: 4, WITCH: 1 }).map(([r]) => r)).toEqual([
    'WEREWOLF',
    'SEER',
    'WITCH',
    'VILLAGER',
  ]);
});

describe('revealRows', () => {
  it('新服务端直接用 players', () => {
    const players = [{ seat: 1, alive: true }];
    expect(revealRows({ players })).toBe(players);
  });

  it('旧版 result 用 roles_cn + lineup 拼', () => {
    const rows = revealRows({
      roles: { '1': 'WEREWOLF', '2': 'SEER' },
      roles_cn: { '1': '狼人', '2': '预言家' },
      alive: [2],
      sheriff: 2,
      death_record: [{ seat: 1, day: 3 }],
      lineup: [{ seat: 1, label: 'Opus' }],
    });
    expect(rows).toMatchObject([
      { seat: 1, side: 'wolf', agent: 'Opus', alive: false, fate_cn: '第3天出局' },
      { seat: 2, side: 'good', alive: true, is_sheriff: true, fate_cn: '存活 · 警长' },
    ]);
  });
});
