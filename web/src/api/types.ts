/**
 * 编排端（werewolf/server.py）返回的数据结构。
 * 只声明前端真正读到的字段；后端多给的字段不影响。
 */

export type GameStatus = 'pending' | 'running' | 'finished' | 'failed' | 'stopped';
export type Winner = 'VILLAGE' | 'WOLF' | null;
export type WinRule = 'edge' | 'city';
export type Audience = 'public' | 'wolves' | 'private' | 'god' | (string & {});

// ─────────── /api/options ───────────

export interface ModelInfo {
  label: string;
  note?: string;
}

export interface BackendInfo {
  label: string;
  models?: Record<string, ModelInfo>;
  custom_model?: boolean;
  needs_key?: string;
}

export interface BoardInfo {
  name: string;
  wolves: number;
  gods: number;
  villagers: number;
  roles?: Record<string, number>;
}

export interface Options {
  boards: Record<string, BoardInfo>;
  backends: Record<string, BackendInfo>;
  keys_present?: Record<string, boolean>;
  efforts: string[];
  /** key → "中文名 —— 说明" */
  deployments: Record<string, string>;
  defaults?: {
    n_players?: number;
    max_speech_chars?: number;
    max_iterations?: number;
    sheriff?: boolean;
    wolf_explode?: boolean;
    deployment?: string;
  };
}

// ─────────── POST /api/games ───────────

export interface SeatPayload {
  seat: number;
  backend: string;
  model: string;
  effort: string;
  base_url: string;
  api_key: string;
  api_key_env: string;
}

export interface CreateGameRequest {
  n_players: number;
  seats: SeatPayload[];
  seed: number | null;
  sheriff: boolean;
  wolf_explode: boolean;
  win_rule: WinRule;
  max_speech_chars: number;
  max_iterations: number;
  deployment: string;
}

// ─────────── 快照 / 事件 ───────────

export interface SnapshotPlayer {
  seat: number;
  alive: boolean;
  is_sheriff: boolean;
  agent?: string;
  role?: string | null;
  role_cn?: string | null;
  revealed_role_cn?: string | null;
  claim?: string | null;
  claim_cn?: string | null;
  died_day?: number | null;
  died_cause?: string | null;
  died_cause_cn?: string | null;
}

export interface CurrentAction {
  seat?: number | null;
  action_type?: string | null;
  action_cn?: string | null;
}

export interface Snapshot {
  id: string;
  status: GameStatus;
  error?: string | null;
  day: number;
  phase: string;
  phase_cn?: string;
  current?: CurrentAction;
  players: SnapshotPlayer[];
  sheriff?: number | null;
  sheriff_status_cn?: string;
  winner?: Winner;
  winner_cn?: string | null;
  speech_progress?: { done: number; total: number } | null;
}

export interface GameEvent {
  type: string;
  text?: string;
  audience?: Audience;
  actor?: number | null;
  phase?: string;
  phase_cn?: string;
  day?: number;
}

export interface EventsResponse {
  events: GameEvent[];
  total?: number;
  snapshot: Snapshot;
}

// ─────────── 复盘 ───────────

export interface LineupSpec {
  seat: number;
  backend?: string;
  model?: string;
  label?: string;
}

export interface RevealPlayer {
  seat: number;
  role?: string;
  role_cn?: string;
  side?: 'wolf' | 'good';
  agent?: string;
  alive: boolean;
  is_sheriff?: boolean;
  fate_cn?: string;
  died_cause_cn?: string;
}

export interface GameResult {
  winner?: Winner;
  winner_cn?: string;
  reason?: string;
  days?: number;
  stats?: { days?: number; n_speeches?: number; n_alive?: number; n_players?: number };
  players?: RevealPlayer[];
  lineup?: LineupSpec[] | null;
  roles?: Record<string, string>;
  roles_cn?: Record<string, string>;
  alive?: number[];
  death_record?: { seat: number; day?: number }[];
  sheriff?: number | null;
  n_thoughts?: number;
}

export interface TimelineRound {
  day: number;
  kind: 'night' | 'day';
  title?: string;
  items?: string[];
}

export interface Thought {
  seat: number;
  day: number;
  phase: string;
  phase_cn?: string;
  action_type: string;
  action_cn?: string;
  action_desc?: string;
  thought: string;
  accepted: boolean;
  attempt?: number;
  error?: string;
}

export interface SessionMessage {
  role: string;
  content: unknown;
}

export interface AgentSession {
  seat: number;
  role?: string;
  role_cn?: string;
  backend?: string;
  backend_cn?: string;
  model?: string;
  release_reason?: string;
  release_reason_cn?: string;
  memory_uri?: string;
  notes?: string;
  system_prompt?: string;
  messages?: SessionMessage[];
}

export interface Replay {
  markdown?: string;
  result?: GameResult;
  thoughts?: Thought[];
  sessions?: AgentSession[];
  timeline?: TimelineRound[];
  duration_s?: number | null;
}

// ─────────── /api/games ───────────

export interface GameListEntry {
  id: string;
  status?: GameStatus;
  created_at?: string | number;
  n_players?: number;
  config?: { n_players?: number };
  board?: { name?: string } | null;
  winner?: Winner;
  winner_cn?: string | null;
  days?: number;
}

export interface GameList {
  live?: GameListEntry[];
  past?: GameListEntry[];
}
