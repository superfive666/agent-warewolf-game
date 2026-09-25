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
  /** 这局有没有真人座位；有真人时进行中锁死上帝视角（服务端强制） */
  has_human?: boolean;
  human_seat?: number | null;
  god_locked?: boolean;
}

/** POST /api/games 的返回：有真人座位时多给一次座位凭证 */
export interface CreatedGame extends Snapshot {
  human?: { seat: number; token: string };
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

// ─────────── 真人座位 /api/games/<id>/seat ───────────

/** 表单选项：value 原样回传给服务端 */
export interface FormOption {
  value: string | number | boolean | null;
  label: string;
}

export interface FormField {
  name: string;
  label: string;
  /** choice 单选 / multi 多选座位 / text / textarea / check 公布验人结果 */
  kind: 'choice' | 'multi' | 'text' | 'textarea' | 'check';
  required: boolean;
  desc?: string;
  /** 可选的次要字段，收进「更多」 */
  advanced?: boolean;
  options?: FormOption[];
  /** kind=check：验人结果的选项 */
  results?: FormOption[];
  max_items?: number | null;
  max_chars?: number;
}

export interface ActionForm {
  action_type: string;
  action_cn: string;
  description: string;
  fields: FormField[];
}

export interface PendingAction {
  request_id: number;
  action_type: string;
  action_cn?: string;
  /** 上一次提交被引擎判为非法时的原因 */
  error?: string | null;
  form: ActionForm | null;
}

export interface ViewEvent {
  seq: number;
  day: number;
  phase_cn?: string;
  type: string;
  vis: Audience;
  text: string;
}

export interface SeatIdentity {
  seat: number;
  role_cn: string;
  faction_cn: string;
  role_brief: string;
  win_condition: string;
  alive: boolean;
  is_sheriff: boolean;
}

export interface SeatView {
  seat: number;
  view: { identity: SeatIdentity; timeline: ViewEvent[] };
  knowledge_cn: string[];
  pending: PendingAction | null;
  released: boolean;
  status: GameStatus;
}

export type ActionPayload = Record<string, unknown>;

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
