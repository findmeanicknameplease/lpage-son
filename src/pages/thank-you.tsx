import React from 'react';
import { CheckCircle, Download } from 'lucide-react';

// This is a standalone component for your /thank-you page.
function ThankYouPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#E9E5F3] to-[#F5F5F5] flex items-center justify-center p-4">
      <div className="max-w-2xl w-full bg-white rounded-2xl shadow-2xl p-8 md:p-12 text-center animate-fade-in">
        <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-6" />
        <h1 className="text-4xl font-bold text-[#0e1116] mb-4">You're on the list!</h1>
        <p className="text-[#0e1116]/70 text-lg mb-8">
            Thank you for your interest. We've received your submission and will be in touch.
        </p>

        <div className="bg-[#e9e5f3]/40 rounded-xl p-6 space-y-6">
          <div>
            <h3 className="font-bold text-lg mb-2">Get a Head Start:</h3>
            <a 
              href="/whatsapp-salon-guide.pdf" // IMPORTANT: Place your PDF guide in the `/public` folder of your project
              download 
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-[#0e1116] text-white rounded-lg font-semibold hover:bg-[#0e1116]/80 transition-all"
            >
              <Download className="w-5 h-5" />
              <span>Download: WhatsApp Booking Guide</span>
            </a>
          </div>
          <div className="border-t border-black/10 pt-6">
            <h3 className="font-bold text-lg mb-2">What happens next?</h3>
            <p className="text-[#0e1116]/70">
                We'll notify you first when early access opens in <span className="font-semibold">Q2 2025</span>.
            </p>
          </div>
        </div>

        <a href="/" className="text-sm text-[#0e1116]/60 hover:underline mt-8 inline-block">
            ← Back to homepage
        </a>
      </div>
    </div>
  );
}

export default ThankYouPage;