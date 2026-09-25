const ROMAN = ['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'];

export const roman = (n: number | null | undefined): string => (n != null && ROMAN[n]) || String(n ?? '');

export const EFFORT_CN: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高',
  xhigh: '超高',
  max: '极限',
};

export const effortCn = (e: string): string => EFFORT_CN[e] ?? e;

export const STATUS_CN: Record<string, string> = {
  pending: '准备中',
  running: '进行中',
  finished: '已结束',
  failed: '出错',
  stopped: '已中止',
};

export const statusCn = (s: string | undefined): string => (s ? (STATUS_CN[s] ?? s) : '');

export const TERMINAL_STATUSES = new Set(['finished', 'failed', 'stopped']);
export const isTerminal = (s: string | undefined): boolean => !!s && TERMINAL_STATUSES.has(s);

export const isNight = (phase: string | undefined | null): boolean => /^NIGHT/.test(phase ?? '');

/** 去掉引擎文本前面的「上帝：」 */
export const stripGod = (t: unknown): string => String(t ?? '').replace(/^上帝：/, '');

/** 秒 → 「42秒」「3:05」「1:02:03」 */
export function fmtDuration(s: number | null | undefined): string | null {
  if (s == null || !Number.isFinite(s)) return null;
  const total = Math.round(s);
  if (total < 60) return `${total}秒`;
  const m = Math.floor(total / 60);
  const r = total % 60;
  const pad = (x: number) => String(x).padStart(2, '0');
  return m >= 60 ? `${Math.floor(m / 60)}:${pad(m % 60)}:${pad(r)}` : `${m}:${pad(r)}`;
}

/** 历史列表里的时间：服务端可能给秒级时间戳，也可能给 ISO 字符串 */
export function fmtCreatedAt(v: string | number | undefined): string {
  if (typeof v === 'number') return new Date(v * 1000).toLocaleString('zh-CN', { hour12: false });
  return String(v ?? '').replace('T', ' ');
}

/** "中文名 —— 说明" → [中文名, 说明] */
export function splitDesc(desc: string): [string, string] {
  const [label = '', hint] = String(desc).split(' —— ');
  return [label, hint ?? label];
}
