import { useEffect, useEffectEvent, useReducer } from 'react';

import { api } from '@/api/games';
import { ApiError } from '@/api/client';
import { isTerminal } from '@/lib/format';

import { EMPTY_SESSION, selectSession, sessionReducer } from './sessionReducer';

export const POLL_MS = 600;

interface Callbacks {
  /** 这局在服务端不存在（比如服务重启前的内存对局） */
  onNotFound: () => void;
  /** 看着它从进行中跑到结束，复盘数据也到了 */
  onFinished: () => void;
}

/**
 * 接入一局对局：轮询增量事件 + 快照，结束后拉一次复盘。
 * gameId 为 null 时什么都不做。
 */
export function useGameSession(gameId: string | null, god: boolean, callbacks: Callbacks) {
  const [state, dispatch] = useReducer(sessionReducer, EMPTY_SESSION);
  const onNotFound = useEffectEvent(callbacks.onNotFound);
  const onFinished = useEffectEvent(callbacks.onFinished);

  // ── 轮询事件。切换视角时 since 归零，从头拉一遍 ──
  useEffect(() => {
    if (!gameId) return;
    const ctl = new AbortController();
    let since = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async () => {
      try {
        const data = await api.events(gameId, since, god, ctl.signal);
        since = data.total ?? since + data.events.length;
        dispatch({ type: 'tick', gameId, god, events: data.events, snapshot: data.snapshot });
        if (isTerminal(data.snapshot.status)) return; // 结束了，不再轮询
      } catch (e) {
        if (ctl.signal.aborted) return;
        if (e instanceof ApiError && e.status === 404) {
          dispatch({ type: 'notFound', gameId });
          onNotFound();
          return;
        }
        console.warn('拉取事件失败，稍后重试', e);
      }
      timer = setTimeout(tick, POLL_MS);
    };

    void tick();
    return () => {
      ctl.abort();
      clearTimeout(timer);
    };
  }, [gameId, god]);

  const mine = gameId != null && state.gameId === gameId;
  const status = mine ? state.snapshot?.status : undefined;
  const needsReplay = mine && !state.replay && (status === 'finished' || status === 'stopped');
  const sawRunning = state.sawRunning;

  // ── 结束后拉一次复盘（与视角无关，所以不依赖 god） ──
  useEffect(() => {
    if (!gameId || !needsReplay) return;
    const ctl = new AbortController();
    api
      .replay(gameId, ctl.signal)
      .then((replay) => {
        dispatch({ type: 'replay', gameId, replay });
        if (sawRunning) onFinished();
      })
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) console.warn('拉取复盘失败', e);
      });
    return () => ctl.abort();
  }, [gameId, needsReplay, sawRunning]);

  return selectSession(state, gameId, god);
}
