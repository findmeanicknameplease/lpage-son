// src/pages/thank-you.tsx

import React from 'react';
import { Link } from 'react-router-dom';
import claxisLogo from '../assets/claxis-logo.png'; // Make sure path is correct
import { CheckCircle } from 'lucide-react';

const ThankYouPage = () => {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#E9E5F3] to-[#F5F5F5] text-[#0e1116] font-sans">
      {/* Consistent Header */}
      <header className="bg-white/50 backdrop-blur-md border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <Link to="/" className="flex items-center space-x-3 w-fit">
            {/* Use standard <img> tag */}
            <img src={claxisLogo} alt="Claxis Logo" className="h-10 w-auto" />
            <span className="text-2xl font-bold text-[#0e1116]">Claxis</span>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="py-16 sm:py-24">
        <div className="max-w-xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-2xl shadow-xl p-8 md:p-12 border border-black/5 text-center">
            <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-6" />
            <h1 className="text-3xl sm:text-4xl font-bold text-[#0e1116] mb-4">
              You're on the list!
            </h1>
            <p className="text-lg text-[#0e1116]/70 mb-8">
              Thank you for joining the waitlist. We're excited to have you on board. We'll send you an email as soon as we're ready to launch.
            </p>
            <Link
              to="/"
              className="px-8 py-3 bg-[#d1ecc5] hover:bg-[#bde4b0] text-[#0e1116] rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all transform hover:scale-105 inline-block"
            >
              Back to Homepage
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ThankYouPage;
