import type { ReactElement } from 'react';

/** 所有图标都是 24×24 的描边 SVG，路径与设计稿一致 */
export const ICON_PATHS = {
  moon: <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z" />,
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
    </>
  ),
  eye: (
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </>
  ),
  lock: (
    <>
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </>
  ),
  wolf: <path d="M4 4l4 5h8l4-5v8l-3 5-5 4-5-4-3-5z" />,
  star: <path d="M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6 6.6 19.5l1.2-6L3.3 9.3l6.1-.7z" />,
  bolt: <path d="M13 3L4 14h7l-1 7 9-11h-7z" />,
  warn: (
    <>
      <path d="M12 3l9.5 17h-19z" />
      <path d="M12 10v4M12 17.5v.1" />
    </>
  ),
  stop: <rect x="6" y="6" width="12" height="12" rx="2" />,
  down: <path d="M12 4v11M7 10l5 5 5-5M5 20h14" />,
  chev: <path d="M6 9l6 6 6-6" />,
  list: (
    <>
      <path d="M4 5h16v14H4z" />
      <path d="M8 9h8M8 13h8M8 17h5" />
    </>
  ),
  redo: (
    <>
      <path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.5" />
      <path d="M4 4v4.5h4.5" />
    </>
  ),
  x: <path d="M6 6l12 12M18 6L6 18" />,
  shield: <path d="M12 1.5l9 3.2v6.6c0 5.8-3.9 9.4-9 11.2-5.1-1.8-9-5.4-9-11.2V4.7z" />,
} satisfies Record<string, ReactElement>;

export type IconName = keyof typeof ICON_PATHS;
