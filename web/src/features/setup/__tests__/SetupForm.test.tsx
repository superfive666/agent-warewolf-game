import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '@/components/toast/ToastProvider';
import { OPTIONS } from '@/test/fixtures';

import { SetupForm } from '../SetupForm';

function renderForm(onStarted = vi.fn()) {
  render(
    <ToastProvider>
      <SetupForm options={OPTIONS} onStarted={onStarted} />
    </ToastProvider>,
  );
  return onStarted;
}

afterEach(() => vi.unstubAllGlobals());

describe('SetupForm', () => {
  it('切换板子后座位数跟着变', async () => {
    renderForm();
    expect(screen.getAllByText(/号位$/)).toHaveLength(12);
    await userEvent.click(
      within(screen.getByRole('radiogroup', { name: '人数' })).getByRole('radio', { name: /9/ }),
    );
    expect(screen.getAllByText(/号位$/)).toHaveLength(9);
  });

  it('套用 Claude 到全部座位后提示缺密钥', async () => {
    renderForm();
    await userEvent.click(screen.getByRole('button', { name: '套用到全部座位' }));
    expect(screen.getByText(/12 个座位用了 Claude/)).toBeInTheDocument();
    expect(screen.getByText('ANTHROPIC_API_KEY')).toBeInTheDocument();
  });

  it('开局成功后回调新对局 id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'g42' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    const onStarted = renderForm();

    await userEvent.click(screen.getByRole('button', { name: /天黑请闭眼/ }));

    expect(onStarted).toHaveBeenCalledWith('g42');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/games');
    expect(JSON.parse(String(init.body))).toMatchObject({ n_players: 12, win_rule: 'edge' });
  });

  it('开局失败时提示服务端的错误信息', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: '配置不合法：x' }), { status: 400 })),
    );
    const onStarted = renderForm();
    await userEvent.click(screen.getByRole('button', { name: /天黑请闭眼/ }));
    expect(await screen.findByText('开局失败：配置不合法：x')).toBeInTheDocument();
    expect(onStarted).not.toHaveBeenCalled();
  });
});
