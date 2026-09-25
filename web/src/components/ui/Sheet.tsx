import { useEffect, useRef, type ReactNode } from 'react';

import { Icon } from './Icon';
import { IconButton } from './IconButton';

interface SheetProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}

/** 模态弹层：桌面居中，手机从底部弹出。基于原生 <dialog>，自带焦点管理和 Esc 关闭 */
export function Sheet({ open, title, onClose, children }: SheetProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    if (!open && dlg.open) dlg.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-label={title}
      onClose={onClose}
      onClick={(e) => {
        // 点遮罩（dialog 自身，而不是里面的内容）关闭
        if (e.target === e.currentTarget) onClose();
      }}
      className={[
        'm-auto max-h-[min(720px,calc(100vh-64px))] w-[min(560px,calc(100vw-32px))] rounded-[18px] border border-line bg-card p-0 text-fg',
        'backdrop:bg-[rgba(6,10,24,.72)]',
        'max-phone:mx-0 max-phone:mt-auto max-phone:mb-0 max-phone:max-h-[85vh] max-phone:w-screen max-phone:max-w-screen max-phone:rounded-t-[18px] max-phone:rounded-b-none max-phone:border-b-0',
      ].join(' ')}
    >
      <div className="sticky top-0 flex items-center justify-between border-b border-rule bg-card pt-4 pr-4 pb-3 pl-6">
        <h2 className="text-21 font-bold text-gold-hi max-phone:text-18">{title}</h2>
        <IconButton aria-label="关闭" onClick={onClose}>
          <Icon name="x" />
        </IconButton>
      </div>
      {children}
    </dialog>
  );
}
