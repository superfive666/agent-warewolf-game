import { useEffect, useState } from 'react';

import { api } from '@/api/games';
import type { Options } from '@/api/types';

/** 拉一次 /api/options（板子、后端、模型、部署模式）。失败时 error 有值。 */
export function useOptions(): { options: Options | null; error: Error | null } {
  const [options, setOptions] = useState<Options | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    api
      .options(ctl.signal)
      .then(setOptions)
      .catch((e: unknown) => {
        if (!ctl.signal.aborted) setError(e instanceof Error ? e : new Error(String(e)));
      });
    return () => ctl.abort();
  }, []);

  return { options, error };
}
