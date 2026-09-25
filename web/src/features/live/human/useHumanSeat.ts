import { useEffect, useState } from 'react';

import { ApiError } from '@/api/client';
import { api } from '@/api/games';
import type { ActionPayload, SeatView } from '@/api/types';
import { isTerminal } from '@/lib/format';
import { loadSeatToken } from '@/lib/seatToken';

export const SEAT_POLL_MS = 800;

/**
 * 真人座位：本机有这局的座位凭证时，轮询自己的视角和待办。
 * 没有凭证（旁观者）时什么都不做，返回 seat = null。
 */
export function useHumanSeat(gameId: string) {
  const token = loadSeatToken(gameId);
  const [data, setData] = useState<{ gameId: string; seat: SeatView } | null>(null);
  // 提交之后立刻重拉一次，不等下一轮
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!token) return;
    const ctl = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    const tick = async () => {
      try {
        const seat = await api.seat(gameId, token, ctl.signal);
        setData({ gameId, seat });
        if (isTerminal(seat.status)) return;
      } catch (e) {
        if (ctl.signal.aborted) return;
        // 凭证不对 / 这局没有真人座位：当旁观者，不再重试
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) return;
        console.warn('拉取座位视角失败，稍后重试', e);
      }
      timer = setTimeout(tick, SEAT_POLL_MS);
    };

    void tick();
    return () => {
      ctl.abort();
      clearTimeout(timer);
    };
  }, [gameId, token, nonce]);

  const submit = async (requestId: number, action: ActionPayload) => {
    if (!token) return;
    await api.act(gameId, token, requestId, action);
    setNonce((n) => n + 1);
  };

  return { seat: data?.gameId === gameId ? data.seat : null, submit };
}
