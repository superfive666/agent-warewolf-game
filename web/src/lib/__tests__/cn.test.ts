import { describe, expect, it } from 'vitest';

import { cn } from '../cn';

describe('cn', () => {
  it('像素字号和文字颜色互不覆盖', () => {
    expect(cn('text-13 text-dim')).toBe('text-13 text-dim');
    expect(cn('text-dim', 'text-13')).toBe('text-dim text-13');
  });

  it('同类后写的覆盖先写的', () => {
    expect(cn('text-13', 'text-12')).toBe('text-12');
    expect(cn('text-dim', 'text-gold-hi')).toBe('text-gold-hi');
    expect(cn('p-7', 'max-phone:p-4', 'p-4')).toBe('max-phone:p-4 p-4');
  });

  it('忽略假值', () => {
    expect(cn('a', false, null, undefined, 'b')).toBe('a b');
  });
});
