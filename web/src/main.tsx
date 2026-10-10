import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { ConsoleApp } from './console/ConsoleApp.tsx';

const isConsoleRoute =
  typeof window !== 'undefined' && window.location.pathname.startsWith('/console');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isConsoleRoute ? <ConsoleApp /> : <App />}
  </StrictMode>
);
