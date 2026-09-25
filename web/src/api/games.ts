import { getJson, postJson } from './client';
import type { CreateGameRequest, EventsResponse, GameList, Options, Replay, Snapshot } from './types';

const game = (id: string) => `/api/games/${encodeURIComponent(id)}`;

export const api = {
  options: (signal?: AbortSignal) => getJson<Options>('/api/options', signal),
  listGames: (signal?: AbortSignal) => getJson<GameList>('/api/games', signal),
  createGame: (body: CreateGameRequest) => postJson<Snapshot>('/api/games', body),
  stopGame: (id: string) => postJson<{ ok: boolean }>(`${game(id)}/stop`),
  events: (id: string, since: number, god: boolean, signal?: AbortSignal) =>
    getJson<EventsResponse>(`${game(id)}/events?since=${since}&god=${god ? 1 : 0}`, signal),
  replay: (id: string, signal?: AbortSignal) => getJson<Replay>(`${game(id)}/replay`, signal),
  /** 逐座位视角原始数据；历史对局没有，会 404 */
  views: (id: string, signal?: AbortSignal) => getJson<unknown>(`${game(id)}/views`, signal),
};
