import { Fragment } from 'react';

import { Icon } from '@/components/ui/Icon';
import { cn } from '@/lib/cn';

import type { LlmUsage } from '../model';

/** 用了 LLM 后端时提示密钥从哪来；两边都没有时标红（开局会被拒） */
export function LlmWarning({ usage }: { usage: LlmUsage }) {
  const error = usage.keyStatus === 'missing';
  return (
    <div
      className={cn(
        'flex gap-3 rounded-xl border border-gold-line bg-notice px-4 py-3.5 text-13 leading-[1.6] text-notice-fg',
        error && 'border-wolf-line bg-wolf-bg text-wolf-soft',
      )}
    >
      <Icon name="warn" className="mt-0.5" />
      <span>
        {usage.counts.map((c) => `${c.count} 个座位用了 ${c.label}`).join('，')}。
        {usage.keyStatus === 'typed' && ' 已在「模型接入」里填了 API Key。'}
        {usage.keyStatus === 'env' && ' 服务端环境里已有密钥。'}
        {error && (
          <>
            {' 服务端没有设置 '}
            {usage.missingEnv.map((env, i) => (
              <Fragment key={env}>
                {i > 0 && ' / '}
                <code className="rounded bg-notice-code px-1.5 py-px font-mono text-12">{env}</code>
              </Fragment>
            ))}
            <b className="font-medium text-wolf-fg">，也没在「模型接入」里填 API Key —— 开局会被拒绝。</b>
          </>
        )}
      </span>
    </div>
  );
}
