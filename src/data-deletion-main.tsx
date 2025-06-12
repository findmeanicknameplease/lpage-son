// src/data-deletion-main.tsx

import React from 'react';
import ReactDOM from 'react-dom/client';
import DataDeletionPage from './pages/data-deletion'; // Your existing page component
import './index.css'; // Import your main styles

// Render the component into the #deletion-root div from data-deletion.html
ReactDOM.createRoot(document.getElementById('deletion-root')!).render(
  <React.StrictMode>
    <DataDeletionPage />
  </React.StrictMode>
);