import { clsx, type ClassValue } from 'clsx';
import { extendTailwindMerge } from 'tailwind-merge';

// 让 tailwind-merge 认识我们按像素命名的字号（text-13 …），否则会把它当颜色和 text-dim 互相覆盖
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: [(v: string) => /^\d+(_\d+)?$/.test(v)] }],
    },
  },
});

/** 合并 className：后写的覆盖先写的（cn('p-4', cond && 'p-2') → 'p-2'） */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
