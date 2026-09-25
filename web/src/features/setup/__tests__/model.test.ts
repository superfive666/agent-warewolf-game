import { describe, expect, it } from 'vitest';

import { OPTIONS } from '@/test/fixtures';

import { buildGameRequest, ctaSubtitle, initialSetup, llmUsage, normalizeSeat, seatSummary } from '../model';
import { setupReducer } from '../useSetupForm';

describe('setup model', () => {
  it('按服务端默认值初始化', () => {
    const s = initialSetup(OPTIONS);
    expect(s.nPlayers).toBe(12);
    expect(s.seats).toHaveLength(12);
    expect(s.maxSpeech).toBe('450');
    expect(s.seats[0]).toEqual({ backend: 'heuristic', model: '', custom: '', effort: 'medium' });
  });

  it('normalizeSeat：模型必须属于当前后端', () => {
    expect(normalizeSeat({ backend: 'claude', model: 'gpt', custom: '', effort: 'low' }, OPTIONS).model).toBe(
      'opus',
    );
    expect(
      normalizeSeat({ backend: 'heuristic', model: 'opus', custom: '', effort: 'low' }, OPTIONS).model,
    ).toBe('');
  });

  it('seatSummary', () => {
    expect(seatSummary({ backend: 'heuristic', model: '', custom: '', effort: 'medium' }, OPTIONS)).toBe(
      '规则 bot',
    );
    expect(seatSummary({ backend: 'claude', model: 'sonnet', custom: '', effort: 'high' }, OPTIONS)).toBe(
      'Claude · Sonnet · 高',
    );
    expect(seatSummary({ backend: 'openai', model: 'gpt', custom: 'qwen', effort: 'low' }, OPTIONS)).toBe(
      'OpenAI · qwen · 低',
    );
  });

  it('改人数时保留已有座位', () => {
    let s = initialSetup(OPTIONS);
    s = setupReducer(s, { type: 'updateSeat', index: 0, patch: { backend: 'claude' }, options: OPTIONS });
    s = setupReducer(s, { type: 'setPlayers', n: 9, options: OPTIONS });
    expect(s.seats).toHaveLength(9);
    expect(s.seats[0]?.backend).toBe('claude');
    expect(s.seats[0]?.model).toBe('opus');
  });

  it('llmUsage：缺密钥时报错，页面填了就放行', () => {
    let s = initialSetup(OPTIONS);
    expect(llmUsage(s, OPTIONS)).toBeNull();
    s = setupReducer(s, {
      type: 'applyAll',
      seat: { backend: 'claude', model: 'opus', custom: '', effort: 'medium' },
      options: OPTIONS,
    });
    expect(llmUsage(s, OPTIONS)).toMatchObject({
      counts: [{ backend: 'claude', count: 12 }],
      keyStatus: 'missing',
      missingEnv: ['ANTHROPIC_API_KEY'],
    });
    s = setupReducer(s, { type: 'set', field: 'apiKey', value: 'sk-x' });
    expect(llmUsage(s, OPTIONS)?.keyStatus).toBe('typed');
  });

  it('buildGameRequest', () => {
    let s = initialSetup(OPTIONS);
    s = setupReducer(s, { type: 'setPlayers', n: 9, options: OPTIONS });
    s = setupReducer(s, { type: 'set', field: 'seed', value: ' 7 ' });
    s = setupReducer(s, { type: 'set', field: 'baseUrl', value: ' https://gw/v1 ' });
    s = setupReducer(s, {
      type: 'updateSeat',
      index: 1,
      patch: { backend: 'openai', custom: 'qwen' },
      options: OPTIONS,
    });
    const req = buildGameRequest(s);
    expect(req).toMatchObject({
      n_players: 9,
      seed: 7,
      win_rule: 'edge',
      max_speech_chars: 450,
      deployment: 'inprocess',
    });
    expect(req.seats).toHaveLength(9);
    expect(req.seats[1]).toEqual({
      seat: 2,
      backend: 'openai',
      model: 'qwen',
      effort: 'medium',
      base_url: 'https://gw/v1',
      api_key: '',
      api_key_env: '',
    });
    expect(buildGameRequest(initialSetup(OPTIONS)).seed).toBeNull();
  });

  it('ctaSubtitle', () => {
    expect(ctaSubtitle(initialSetup(OPTIONS), OPTIONS)).toBe('12 人 · 屠边 · 同进程 · 开局后全自动跑完');
  });
});
