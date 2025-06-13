// src/App.tsx

import React from 'react';
import { Routes, Route } from 'react-router-dom';

// --- Import all your page components ---
import LandingPage from './LandingPage'; 
import DataDeletionPage from './pages/data-deletion';
import ThankYouPage from './pages/thank-you'; 

/**
 * This App component is now just a route switcher.
 * The routing context is provided by BrowserRouter in main.tsx.
 */
function App() {
  return (
    <Routes>
      {/* Route for the main landing page */}
      <Route path="/" element={<LandingPage />} />
      
      {/* Route for the data deletion page */}
      <Route path="/data-deletion.html" element={<DataDeletionPage />} />

      {/* Route for the thank you page */}
      <Route path="/thank-you" element={<ThankYouPage />} />

      {/* Optional: Add a 404 Not Found page as a fallback */}
      {/* <Route path="*" element={<NotFoundPage />} /> */}
    </Routes>
  );
}

export default App;