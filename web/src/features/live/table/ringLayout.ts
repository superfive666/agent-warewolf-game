/** 第 i 个座位在圆桌上的位置（百分比）。1 号在正上方，顺时针排开 */
export function ringPosition(i: number, n: number, compact: boolean): { left: string; top: string } {
  const cy = 47; // 圆桌中心略靠上，给最下面座位的标签留位置
  const rx = compact ? 38.5 : 40.5;
  const ry = compact ? 38 : 39;
  const a = ((-90 + (i * 360) / n) * Math.PI) / 180;
  return { left: `${50 + rx * Math.cos(a)}%`, top: `${cy + ry * Math.sin(a)}%` };
}
