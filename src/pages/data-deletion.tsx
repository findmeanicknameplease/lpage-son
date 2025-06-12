// src/pages/data-deletion.tsx

import React from 'react';
import { Link } from 'react-router-dom'; // Use react-router-dom's Link
import claxisLogo from '../assets/claxis-logo.png'; // Make sure this path is correct

// This is a standard React functional component, not a NextPage
const DataDeletionPage = () => {
  return (
    // We removed the <Head> component as it's a Next.js feature
    <div className="min-h-screen bg-gradient-to-b from-[#E9E5F3] to-[#F5F5F5] text-[#0e1116] font-sans">
      {/* Consistent Header */}
      <header className="bg-white/50 backdrop-blur-md border-b border-black/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <Link to="/" className="flex items-center space-x-3 w-fit">
            {/* We use a standard <img> tag instead of Next.js's <Image> */}
            <img src={claxisLogo} alt="Claxis Logo" className="h-10 w-auto" />
            <span className="text-2xl font-bold text-[#0e1116]">Claxis</span>
          </Link>
        </div>
      </header>

      {/* Main Content (this part remains the same) */}
      <main className="py-16 sm:py-24">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-2xl shadow-xl p-8 md:p-12 border border-black/5">
            <h1 className="text-3xl sm:text-4xl font-bold text-[#0e1116] mb-4">
              Data Deletion Instructions
            </h1>
            <p className="text-lg text-[#0e1116]/70 mb-8">
              At Claxis, we are committed to protecting your privacy. This page provides instructions on how to request the deletion of your data from our systems, in accordance with Facebook's Platform Terms.
            </p>

            <div className="space-y-6 text-[#0e1116]/80 leading-relaxed">
              <section>
                <h2 className="text-2xl font-semibold text-[#0e1116] mb-3">What Data We Collect</h2>
                <p>
                  Claxis is a service that connects to your WhatsApp to facilitate appointment bookings. The personal data we store is limited to what is necessary for this function. This may include:
                </p>
                <ul className="list-disc list-inside mt-2 space-y-1 pl-4">
                  <li>Your Name (as provided or from your WhatsApp profile)</li>
                  <li>Your WhatsApp Phone Number</li>
                  <li>Appointment Details (service, date, time)</li>
                  <li>Conversation history related to booking, rescheduling, or canceling appointments</li>
                </ul>
              </section>

              <section>
                <h2 className="text-2xl font-semibold text-[#0e1116] mb-3">How to Request Data Deletion</h2>
                <p>
                  To request the deletion of your data, please follow these simple steps:
                </p>
                <ol className="list-decimal list-inside mt-4 space-y-3 pl-4 bg-[#e9e5f3]/30 p-6 rounded-lg border border-black/5">
                  <li>
                    Compose a new email using your preferred email client.
                  </li>
                  <li>
                    Send the email to our dedicated support address: <a href="mailto:hello@getclaxis.com" className="font-semibold text-blue-600 hover:underline">hello@getclaxis.com</a>
                  </li>
                  <li>
                    Use the following subject line: <strong className="font-semibold text-black">"Data Deletion Request"</strong>
                  </li>
                  <li>
                    In the body of the email, please include the <strong className="font-semibold text-black">WhatsApp phone number</strong> associated with the data you wish to have deleted. This is required for us to identify your records.
                  </li>
                </ol>
              </section>

              <section>
                <h2 className="text-2xl font-semibold text-[#0e1116] mb-3">What to Expect Next</h2>
                <p>
                  Once we receive your request, we will first send an email to acknowledge it. We will then process your request and permanently delete all associated data from our production databases within 14 business days. You will receive a final confirmation email once the deletion is complete.
                </p>
              </section>
            </div>
          </div>
        </div>
      </main>
      
      {/* Consistent Footer */}
      <footer className="px-4 py-8 bg-[#0e1116] text-white">
        <div className="max-w-6xl mx-auto text-center text-sm text-white/40">
          <p>© 2025 Eat Sleep Shop Repeat, LLC. All rights reserved.</p>
          <p className="mt-2">
            Claxis is an independent product and is not affiliated with, endorsed, or sponsored by Meta Platforms, Inc.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default DataDeletionPage;
