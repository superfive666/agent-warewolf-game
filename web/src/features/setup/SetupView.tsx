import { useEffect } from 'react';

import { Hint } from '@/components/ui/Card';
import { useToast } from '@/components/toast/useToast';
import { useOptions } from '@/hooks/useOptions';

import { Hero } from './components/Hero';
import { SetupForm } from './SetupForm';

interface SetupViewProps {
  hidden: boolean;
  onStarted: (gameId: string) => void;
}

/**
 * 第一步：配置牌局。
 * 切到别的步骤时只是隐藏（不卸载），这样回来时刚才填的配置还在。
 */
export function SetupView({ hidden, onStarted }: SetupViewProps) {
  const { options, error } = useOptions();
  const toast = useToast();

  useEffect(() => {
    if (error) toast(`连不上服务端：${error.message}`, 10000);
  }, [error, toast]);

  return (
    <section hidden={hidden}>
      <Hero />
      {options ? (
        <SetupForm options={options} onStarted={onStarted} />
      ) : (
        <Hint className="block px-gutter py-10">{error ? '连不上服务端。' : '加载中…'}</Hint>
      )}
    </section>
  );
}
