/**
 * 真人座位的纯逻辑：表单初值、拼动作、提交前检查、挑出私密信息。
 * 表单结构（字段、选项、中文名）全部由服务端给，这里只管照着组装。
 */
import type { ActionForm, ActionPayload, FormField, FormOption, ViewEvent } from '@/api/types';

export type FieldValue = FormOption['value'] | number[] | CheckValue | undefined;

export interface CheckValue {
  target: number | null;
  result: string | null;
}

export type FormValues = Record<string, FieldValue>;

const hasNull = (f: FormField) => (f.options ?? []).some((o) => o.value === null);

/** 初值：只有一个选项就直接选上；能选「空」的默认选「空」（弃票 / 不起跳 / 不用毒）；布尔默认「否」 */
export function initialValue(f: FormField): FieldValue {
  const opts = f.options ?? [];
  switch (f.kind) {
    case 'choice':
      if (opts.length === 1) return opts[0]?.value;
      if (opts.some((o) => o.value === false)) return false;
      return hasNull(f) ? null : undefined;
    case 'multi':
      return [];
    case 'check':
      return { target: null, result: null };
    default:
      return '';
  }
}

export function initialValues(form: ActionForm): FormValues {
  return Object.fromEntries(form.fields.map((f) => [f.name, initialValue(f)]));
}

/** 提交前能在前端发现的问题（引擎还会再校验一遍） */
export function formProblems(form: ActionForm, values: FormValues): string[] {
  const out: string[] = [];
  for (const f of form.fields) {
    const v = values[f.name];
    if (f.kind === 'choice' && v === undefined) out.push(`请选择「${f.label}」`);
    if (f.kind === 'textarea' && typeof v === 'string') {
      if (f.required && !v.trim()) out.push(`请填写「${f.label}」`);
      if (f.max_chars && v.length > f.max_chars) out.push(`「${f.label}」超过 ${f.max_chars} 字`);
    }
    if (f.kind === 'check') {
      const c = v as CheckValue;
      if ((c.target === null) !== (c.result === null)) out.push(`「${f.label}」要同时选座位和结果`);
    }
  }
  return out;
}

/** 表单值 → 交给服务端的动作。没填的可选字段不发 */
export function buildAction(form: ActionForm, values: FormValues): ActionPayload {
  const out: ActionPayload = {};
  for (const f of form.fields) {
    const v = values[f.name];
    if (v === undefined) continue;
    if (f.kind === 'text' || f.kind === 'textarea') {
      const text = String(v).trim();
      if (text) out[f.name] = text;
    } else if (f.kind === 'check') {
      const c = v as CheckValue;
      out[f.name] = c.target !== null && c.result !== null ? { target: c.target, result: c.result } : null;
    } else {
      out[f.name] = v;
    }
  }
  return out;
}

/** 只有我能看到的事件（狼人频道、验人结果、用药……）；公开事件在实况里已经有了 */
export function privateEvents(timeline: ViewEvent[], limit = 12): ViewEvent[] {
  return timeline.filter((e) => e.vis !== 'public').slice(-limit);
}
