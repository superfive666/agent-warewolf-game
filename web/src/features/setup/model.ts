/**
 * 配置页的纯逻辑：座位规范化、摘要文案、LLM 密钥检查、拼开局请求。
 * 不碰 React，方便单测。
 */
import type { CreateGameRequest, ModelInfo, Options, WinRule } from '@/api/types';
import { effortCn, splitDesc } from '@/lib/format';

export interface SeatConfig {
  backend: string;
  /** 下拉框选中的模型 key；该后端没有模型列表时为空 */
  model: string;
  /** openai 兼容网关可以填任意模型名，优先于 model */
  custom: string;
  effort: string;
}

export interface SetupState {
  nPlayers: number;
  seats: SeatConfig[];
  winRule: WinRule;
  deployment: string;
  sheriff: boolean;
  explode: boolean;
  /** 数字输入框保留原始字符串，提交时再转 */
  maxSpeech: string;
  maxIter: string;
  seed: string;
  baseUrl: string;
  apiKey: string;
  apiKeyEnv: string;
}

/** 真人玩家座位的后端 key。一桌最多一个 */
export const HUMAN_BACKEND = 'human';

export const DEFAULT_SEAT: SeatConfig = { backend: 'heuristic', model: '', custom: '', effort: 'medium' };

export function initialSetup(options: Options | null): SetupState {
  const d = options?.defaults ?? {};
  const n = d.n_players ?? 12;
  return {
    nPlayers: n,
    seats: Array.from({ length: n }, () => normalizeSeat(DEFAULT_SEAT, options)),
    winRule: 'edge',
    deployment: d.deployment ?? 'inprocess',
    sheriff: d.sheriff !== false,
    explode: d.wolf_explode !== false,
    maxSpeech: String(d.max_speech_chars ?? 450),
    maxIter: String(d.max_iterations ?? 3),
    seed: '',
    baseUrl: '',
    apiKey: '',
    apiKeyEnv: '',
  };
}

export function backendModels(options: Options | null, backend: string): Record<string, ModelInfo> {
  return options?.backends[backend]?.models ?? {};
}

/** 这个后端有没有「模型 / 思考强度」可选 */
export function hasModelChoice(options: Options | null, backend: string): boolean {
  return (
    Object.keys(backendModels(options, backend)).length > 0 || !!options?.backends[backend]?.custom_model
  );
}

/** 模型 key 必须属于当前后端；没有模型列表的后端清空 */
export function normalizeSeat(seat: SeatConfig, options: Options | null): SeatConfig {
  const keys = Object.keys(backendModels(options, seat.backend));
  if (!keys.length) return seat.model ? { ...seat, model: '' } : seat;
  if (!keys.includes(seat.model)) return { ...seat, model: keys[0] ?? '' };
  return seat;
}

/** 手机上折叠后显示的一行摘要：「Claude · Opus · 中」 */
export function seatSummary(seat: SeatConfig, options: Options | null): string {
  const b = options?.backends[seat.backend];
  const models = backendModels(options, seat.backend);
  const withModel = hasModelChoice(options, seat.backend);
  const model = seat.custom || models[seat.model]?.label || seat.model;
  return [b?.label ?? seat.backend, withModel ? model : null, withModel ? effortCn(seat.effort) : null]
    .filter(Boolean)
    .join(' · ');
}

export function resizeSeats(seats: SeatConfig[], n: number, options: Options | null): SeatConfig[] {
  return Array.from({ length: n }, (_, i) => seats[i] ?? normalizeSeat(DEFAULT_SEAT, options));
}

// ─────────── LLM 密钥检查 ───────────

export interface LlmUsage {
  /** 各个 LLM 后端用了几个座位 */
  counts: { backend: string; label: string; count: number }[];
  /** 'typed' 页面上填了 key；'missing' 服务端也没有 → 开局会被拒；'env' 服务端环境里有 */
  keyStatus: 'typed' | 'missing' | 'env';
  /** 缺的环境变量名 */
  missingEnv: string[];
}

export function llmUsage(
  state: Pick<SetupState, 'seats' | 'apiKey'>,
  options: Options | null,
): LlmUsage | null {
  if (!options) return null;
  const counts = new Map<string, number>();
  for (const s of state.seats) {
    // 规则 bot、真人座位不调模型，不需要密钥
    if (options.backends[s.backend]?.needs_key) counts.set(s.backend, (counts.get(s.backend) ?? 0) + 1);
  }
  if (!counts.size) return null;
  const used = [...counts.keys()];
  const missing = used.filter((b) => options.keys_present?.[b] === false);
  const keyStatus = state.apiKey.trim() ? 'typed' : missing.length ? 'missing' : 'env';
  return {
    counts: used.map((b) => ({
      backend: b,
      label: options.backends[b]?.label ?? b,
      count: counts.get(b) ?? 0,
    })),
    keyStatus,
    missingEnv: missing.map((b) => options.backends[b]?.needs_key ?? b),
  };
}

// ─────────── 真人座位 ───────────

/** 选了真人玩家的座位号（从 1 开始） */
export function humanSeats(seats: SeatConfig[]): number[] {
  return seats.flatMap((s, i) => (s.backend === HUMAN_BACKEND ? [i + 1] : []));
}

// ─────────── 开局 ───────────

export function ctaSubtitle(state: SetupState, options: Options | null): string {
  const [dep] = splitDesc(options?.deployments[state.deployment] ?? state.deployment);
  const [human] = humanSeats(state.seats);
  const tail = human ? `你坐 ${human} 号` : '开局后全自动跑完';
  return `${state.nPlayers} 人 · ${state.winRule === 'city' ? '屠城' : '屠边'} · ${dep} · ${tail}`;
}

export function buildGameRequest(state: SetupState): CreateGameRequest {
  const baseUrl = state.baseUrl.trim();
  const apiKeyEnv = state.apiKeyEnv.trim();
  const seed = state.seed.trim();
  return {
    n_players: state.nPlayers,
    // 挂自己的 provider 的三件套：base_url + model + api_key。
    // 密钥只用于这一次请求 —— 服务端不会把它写进会话库，也不会回传给页面。
    seats: state.seats.map((s, i) => ({
      seat: i + 1,
      backend: s.backend,
      model: s.custom || s.model,
      effort: s.effort,
      base_url: baseUrl,
      api_key: state.apiKey,
      api_key_env: apiKeyEnv,
    })),
    seed: seed === '' ? null : Number(seed),
    sheriff: state.sheriff,
    wolf_explode: state.explode,
    win_rule: state.winRule,
    max_speech_chars: Number(state.maxSpeech),
    max_iterations: Number(state.maxIter),
    deployment: state.deployment,
  };
}
