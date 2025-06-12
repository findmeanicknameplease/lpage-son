// src/App.tsx

import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';

// --- Import all your page components ---
// This is the landing page code you moved in Step 1.
import LandingPage from './LandingPage'; 

// These are the pages you created for Meta verification and the form redirect.
// Make sure they are in a '/pages' directory as discussed.
import DataDeletionPage from './pages/data-deletion';
import ThankYouPage from './pages/thank-you'; 

/**
 * This App component now acts as the main router for your application.
 * It doesn't contain any visible content itself. Instead, it decides which
 * full-page component to render based on the URL in the browser.
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Route 1: The Homepage */}
        {/* When the URL is "/", it will render the LandingPage component. */}
        <Route path="/" element={<LandingPage />} />

        {/* Route 2: The Data Deletion Page */}
        {/* When the URL is "/data-deletion", it will render the DataDeletionPage component. */}
        <Route path="/data-deletion" element={<DataDeletionPage />} />
        
        {/* Route 3: The Thank You Page */}
        {/* When the URL is "/thank-you", it will render the ThankYouPage component. */}
        <Route path="/thank-you" element={<ThankYouPage />} />

        {/* Optional: You could add a "Not Found" page for any other URL */}
        {/* <Route path="*" element={<NotFoundPage />} /> */}
      </Routes>
    </BrowserRouter>
  );
}

export default App;