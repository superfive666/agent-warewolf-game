/**
 * 真人座位的凭证：开局时服务端只给一次，存在本机，刷新页面还能接着打。
 * 存储不可用（隐私模式等）时退化为只在内存里记着，这一页关掉就只能旁观了。
 */
const KEY = (gameId: string) => `werewolf:seat-token:${gameId}`;
const memory = new Map<string, string>();

export function saveSeatToken(gameId: string, token: string): void {
  memory.set(gameId, token);
  try {
    localStorage.setItem(KEY(gameId), token);
  } catch {
    // 只留内存里那份
  }
}

export function loadSeatToken(gameId: string): string | null {
  try {
    const t = localStorage.getItem(KEY(gameId));
    if (t) return t;
  } catch {
    // 读不到就看内存
  }
  return memory.get(gameId) ?? null;
}
