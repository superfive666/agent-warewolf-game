import { createContext } from 'react';

export type ShowToast = (message: string, ms?: number) => void;

export const ToastContext = createContext<ShowToast | null>(null);
