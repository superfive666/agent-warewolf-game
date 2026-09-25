import { describe, expect, it } from 'vitest';

import type { ActionForm, ViewEvent } from '@/api/types';

import { buildAction, formProblems, initialValues, privateEvents } from '../model';

const SPEECH: ActionForm = {
  action_type: 'speech',
  action_cn: '发言',
  description: '轮到你发言了。',
  fields: [
    { name: 'speech', label: '发言', kind: 'textarea', required: true, max_chars: 10 },
    {
      name: 'claim',
      label: '宣称身份',
      kind: 'choice',
      required: false,
      options: [
        { value: 'SEER', label: '预言家' },
        { value: null, label: '不起跳' },
      ],
    },
    {
      name: 'claimed_check',
      label: '公布验人结果',
      kind: 'check',
      required: false,
      options: [{ value: 2, label: '2号' }],
      results: [{ value: 'WOLF', label: '查杀' }],
    },
    { name: 'badge_flow', label: '警徽流', kind: 'multi', required: false, options: [], max_items: 3 },
    {
      name: 'explode',
      label: '自爆',
      kind: 'choice',
      required: false,
      options: [
        { value: true, label: '自爆' },
        { value: false, label: '不自爆' },
      ],
    },
    { name: 'claim_detail', label: '补充说明', kind: 'text', required: false, advanced: true },
  ],
};

const CHECK: ActionForm = {
  action_type: 'seer_check',
  action_cn: '预言家验人',
  description: '',
  fields: [
    {
      name: 'target',
      label: '目标',
      kind: 'choice',
      required: false,
      options: [
        { value: 4, label: '4号' },
        { value: 5, label: '5号' },
      ],
    },
  ],
};

describe('真人座位表单', () => {
  it('初值：能选「空」默认空，布尔默认否，没得空选就得自己挑', () => {
    expect(initialValues(SPEECH)).toEqual({
      speech: '',
      claim: null,
      claimed_check: { target: null, result: null },
      badge_flow: [],
      explode: false,
      claim_detail: '',
    });
    expect(initialValues(CHECK)).toEqual({ target: undefined });
  });

  it('提交前检查：必填、字数、验人结果要成对', () => {
    const v = initialValues(SPEECH);
    expect(formProblems(SPEECH, v)).toEqual(['请填写「发言」']);
    expect(formProblems(SPEECH, { ...v, speech: '一二三四五六七八九十十一' })).toEqual([
      '「发言」超过 10 字',
    ]);
    expect(formProblems(SPEECH, { ...v, speech: '好', claimed_check: { target: 2, result: null } })).toEqual([
      '「公布验人结果」要同时选座位和结果',
    ]);
    expect(formProblems(CHECK, initialValues(CHECK))).toEqual(['请选择「目标」']);
  });

  it('拼动作：空文本不发，验人结果成对才发', () => {
    const v = {
      ...initialValues(SPEECH),
      speech: ' 我是预言家 ',
      claim: 'SEER',
      claimed_check: { target: 2, result: 'WOLF' },
      badge_flow: [4, 5],
    };
    expect(buildAction(SPEECH, v)).toEqual({
      speech: '我是预言家',
      claim: 'SEER',
      claimed_check: { target: 2, result: 'WOLF' },
      badge_flow: [4, 5],
      explode: false,
    });
    expect(buildAction(SPEECH, initialValues(SPEECH)).claimed_check).toBeNull();
    expect(buildAction(CHECK, { target: 5 })).toEqual({ target: 5 });
  });

  it('私密消息只挑非公开事件', () => {
    const ev = (seq: number, vis: string): ViewEvent => ({ seq, day: 1, type: 't', vis, text: String(seq) });
    const out = privateEvents([ev(1, 'public'), ev(2, 'private'), ev(3, 'wolves'), ev(4, 'public')]);
    expect(out.map((e) => e.seq)).toEqual([2, 3]);
  });
});
