import { describe, expect, it } from 'vitest';

import { fmtDuration, isNight, isTerminal, roman, splitDesc, stripGod } from '../format';

describe('format', () => {
  it('fmtDuration', () => {
    expect(fmtDuration(null)).toBeNull();
    expect(fmtDuration(Number.NaN)).toBeNull();
    expect(fmtDuration(42.4)).toBe('42秒');
    expect(fmtDuration(185)).toBe('3:05');
    expect(fmtDuration(3723)).toBe('1:02:03');
  });

  it('roman', () => {
    expect(roman(1)).toBe('I');
    expect(roman(12)).toBe('XII');
    expect(roman(13)).toBe('13');
    expect(roman(0)).toBe('0');
  });

  it('isNight / isTerminal / stripGod / splitDesc', () => {
    expect(isNight('NIGHT_WOLF')).toBe(true);
    expect(isNight('DAY_SPEECH')).toBe(false);
    expect(isTerminal('stopped')).toBe(true);
    expect(isTerminal('running')).toBe(false);
    expect(stripGod('上帝：天亮了')).toBe('天亮了');
    expect(splitDesc('同进程 —— 最快')).toEqual(['同进程', '最快']);
    expect(splitDesc('只有名字')).toEqual(['只有名字', '只有名字']);
  });
});
