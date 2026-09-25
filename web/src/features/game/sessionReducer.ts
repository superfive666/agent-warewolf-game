import type { GameEvent, Replay, Snapshot } from '@/api/types';
import { isTerminal } from '@/lib/format';

/**
 * 一局对局在前端的全部状态。
 * gameId / god 记录这份数据是「哪一局、哪个视角」拉来的：
 * 切到别的对局或切换上帝视角时，旧数据自动作废，不需要在 effect 里手动清空。
 */
export interface SessionState {
  gameId: string | null;
  god: boolean;
  events: GameEvent[];
  snapshot: Snapshot | null;
  replay: Replay | null;
  notFound: boolean;
  /** 接入时对局还在跑 → 结束时自动跳到复盘 */
  sawRunning: boolean;
}

export type SessionAction =
  | { type: 'tick'; gameId: string; god: boolean; events: GameEvent[]; snapshot: Snapshot }
  | { type: 'replay'; gameId: string; replay: Replay }
  | { type: 'notFound'; gameId: string };

export const EMPTY_SESSION: SessionState = {
  gameId: null,
  god: false,
  events: [],
  snapshot: null,
  replay: null,
  notFound: false,
  sawRunning: false,
};

export function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case 'tick': {
      if (action.gameId !== state.gameId) {
        return {
          ...EMPTY_SESSION,
          gameId: action.gameId,
          god: action.god,
          events: action.events,
          snapshot: action.snapshot,
          sawRunning: !isTerminal(action.snapshot.status),
        };
      }
      // 视角变了：事件从头拉，替换而不是追加
      const events = action.god === state.god ? [...state.events, ...action.events] : action.events;
      return { ...state, god: action.god, events, snapshot: action.snapshot };
    }
    case 'replay':
      return action.gameId === state.gameId ? { ...state, replay: action.replay } : state;
    case 'notFound':
      return { ...EMPTY_SESSION, gameId: action.gameId, notFound: true };
  }
}

/** 从 reducer 状态里取出「当前这一局、当前视角」真正可用的数据 */
export function selectSession(state: SessionState, gameId: string | null, god: boolean) {
  const mine = gameId != null && state.gameId === gameId;
  return {
    snapshot: mine ? state.snapshot : null,
    events: mine && state.god === god ? state.events : [],
    replay: mine ? state.replay : null,
  };
}
