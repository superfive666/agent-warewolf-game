import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { ToastProvider } from './components/toast/ToastProvider';
import './styles/index.css';

const root = document.getElementById('root');
if (!root) throw new Error('index.html 里缺少 #root');

createRoot(root).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
);
