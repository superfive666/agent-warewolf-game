import { describe, expect, it } from 'vitest';

import { snapshot } from '@/test/fixtures';

import { EMPTY_SESSION, selectSession, sessionReducer } from '../sessionReducer';

const e = (text: string) => ({ type: 'system', text });

describe('sessionReducer', () => {
  it('同一局同一视角：事件追加', () => {
    let s = sessionReducer(EMPTY_SESSION, {
      type: 'tick',
      gameId: 'g',
      god: false,
      events: [e('a')],
      snapshot: snapshot(),
    });
    s = sessionReducer(s, { type: 'tick', gameId: 'g', god: false, events: [e('b')], snapshot: snapshot() });
    expect(s.events.map((x) => x.text)).toEqual(['a', 'b']);
    expect(s.sawRunning).toBe(true);
  });

  it('切换视角：事件替换', () => {
    let s = sessionReducer(EMPTY_SESSION, {
      type: 'tick',
      gameId: 'g',
      god: false,
      events: [e('a')],
      snapshot: snapshot(),
    });
    s = sessionReducer(s, {
      type: 'tick',
      gameId: 'g',
      god: true,
      events: [e('A'), e('B')],
      snapshot: snapshot(),
    });
    expect(s.events.map((x) => x.text)).toEqual(['A', 'B']);
  });

  it('换一局：全部重来，复盘清空', () => {
    let s = sessionReducer(EMPTY_SESSION, {
      type: 'tick',
      gameId: 'g1',
      god: false,
      events: [e('a')],
      snapshot: snapshot({ status: 'finished' }),
    });
    s = sessionReducer(s, { type: 'replay', gameId: 'g1', replay: { markdown: '#' } });
    expect(s.replay).not.toBeNull();
    expect(s.sawRunning).toBe(false);
    s = sessionReducer(s, { type: 'tick', gameId: 'g2', god: false, events: [], snapshot: snapshot() });
    expect(s.replay).toBeNull();
    expect(s.events).toEqual([]);
  });

  it('迟到的旧局复盘被丢弃', () => {
    const s = sessionReducer(EMPTY_SESSION, {
      type: 'tick',
      gameId: 'g2',
      god: false,
      events: [],
      snapshot: snapshot(),
    });
    expect(sessionReducer(s, { type: 'replay', gameId: 'g1', replay: {} })).toBe(s);
  });

  it('selectSession 只返回当前局 / 当前视角的数据', () => {
    const s = sessionReducer(EMPTY_SESSION, {
      type: 'tick',
      gameId: 'g',
      god: false,
      events: [e('a')],
      snapshot: snapshot(),
    });
    expect(selectSession(s, 'g', false).events).toHaveLength(1);
    expect(selectSession(s, 'g', true).events).toHaveLength(0);
    expect(selectSession(s, 'other', false).snapshot).toBeNull();
  });
});
