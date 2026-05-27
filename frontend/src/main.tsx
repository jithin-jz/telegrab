import { setupGlobalErrorForwarding } from './lib/errorReporter';

// Register global error forwarding as early as possible, before React renders.
setupGlobalErrorForwarding();

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
