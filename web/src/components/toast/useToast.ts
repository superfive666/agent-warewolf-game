import { useContext } from 'react';

import { ToastContext, type ShowToast } from './ToastContext';

export function useToast(): ShowToast {
  const show = useContext(ToastContext);
  if (!show) throw new Error('useToast 必须在 <ToastProvider> 里面用');
  return show;
}
