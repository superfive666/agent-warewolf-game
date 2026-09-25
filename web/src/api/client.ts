/**
 * 所有 HTTP 请求的唯一出口。
 *
 * VITE_API_BASE 留空 = 同源（nginx 镜像反代 /api，或 werewolf-server 直接托管）。
 * 纯静态部署到别的域名时，构建前设成编排端地址即可。
 */
const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/+$/, '');

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(API_BASE + path, init);
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // 非 JSON 响应：交给下面按状态码处理
  }
  if (!res.ok) {
    const msg =
      data && typeof data === 'object' && 'error' in data ? String(data.error) : `HTTP ${res.status}`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal });
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
