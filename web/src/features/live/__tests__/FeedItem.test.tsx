import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { FeedItem } from '../feed/FeedItem';

describe('FeedItem', () => {
  it('发言渲染成气泡，去掉前缀', () => {
    render(
      <FeedItem
        event={{ type: 'speech', actor: 3, audience: 'public', text: '3号：我是预言家' }}
        agent="Opus"
      />,
    );
    expect(screen.getByText('我是预言家')).toBeInTheDocument();
    expect(screen.getByText(/3 号 · Opus/)).toBeInTheDocument();
  });

  it('上帝视角才显示真实身份', () => {
    render(<FeedItem event={{ type: 'speech', actor: 3, text: '过' }} roleCn="狼人" />);
    expect(screen.getByText(/· 狼人/)).toBeInTheDocument();
  });

  it('阶段分隔线', () => {
    render(<FeedItem event={{ type: 'phase', phase: 'NIGHT_WOLF', text: '—— 第 1 夜 —— 天黑请闭眼' }} />);
    expect(screen.getByText('第 1 夜 · 天黑请闭眼')).toBeInTheDocument();
  });

  it('狼人频道的非发言消息', () => {
    render(
      <FeedItem
        event={{ type: 'wolf_kill', audience: 'wolves', phase_cn: '狼人行动', text: '上帝：刀 5 号' }}
      />,
    );
    expect(screen.getByText('狼人频道 · 狼人行动')).toBeInTheDocument();
    expect(screen.getByText('刀 5 号')).toBeInTheDocument();
  });

  it('文本一律按纯文本渲染（不解析 HTML）', () => {
    const { container } = render(
      <FeedItem event={{ type: 'system', text: '<img src=x onerror=alert(1)>' }} />,
    );
    expect(container.querySelector('img')).toBeNull();
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
  });
});
