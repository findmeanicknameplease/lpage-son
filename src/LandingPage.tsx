import React, { useState, useEffect, useRef } from 'react';
import { Calendar, MessageCircle, Shield, CheckCircle, ArrowRight, Star, Lock, Phone, Mail,  TrendingUp, DollarSign, HeartHandshake, Award, Menu, X, Loader2,  Building } from 'lucide-react';

// Import your logo
import claxisLogo from './assets/claxis-logo.png'; 

// --- DISCLAIMER: IMPORTANT ---
// The following legal text is for informational purposes only and does not constitute legal advice.
// It is a basic template for a pre-launch product. You should consult with a qualified
// legal professional to ensure your policies are complete and compliant with all applicable laws.

// --- TYPE DEFINITIONS ---
interface Message { id: number; sender: 'user' | 'ai'; content: React.ReactNode; isTyping?: boolean; }
interface Testimonial { id: number; name: string; business: string; location: string; review: string; avatar: string; }
type ActiveModal = 'privacy' | 'terms' | null;

// --- MOCK DATA (No Changes) ---
const conversationScript: Message[] = [ { id: 1, sender: 'user', content: <p>Hi! I'd like to book a balayage for Friday afternoon 💇‍♀️</p> }, { id: 2, sender: 'ai', isTyping: true, content: <></> }, { id: 3, sender: 'ai', content: <p>Hello! Let me check our availability for Friday...</p> }, { id: 4, sender: 'ai', isTyping: true, content: <></> }, { id: 5, sender: 'ai', content: ( <> <p>Great news! I have these times available with Sarah:</p> <div className="mt-3 space-y-2"> <button className="w-full bg-black/5 hover:bg-black/10 transition-colors rounded-lg px-3 py-2 text-sm text-left">📅 Friday 2:00 PM</button> <button className="w-full bg-black/5 hover:bg-black/10 transition-colors rounded-lg px-3 py-2 text-sm text-left">📅 Friday 3:30 PM</button> </div> </> )}, { id: 6, sender: 'user', content: <p>3:30 would be perfect!</p> }, { id: 7, sender: 'ai', isTyping: true, content: <></> }, { id: 8, sender: 'ai', content: ( <> <p className="font-medium mb-2">✅ Appointment Confirmed!</p> <div className="bg-black/10 rounded-lg p-3 text-sm"> <p><strong>Balayage with Sarah</strong></p> <p>📅 Friday, June 20th @ 3:30 PM</p> </div> <p className="text-sm mt-3">See you then!</p> </> )}, ];
const testimonials: Testimonial[] = [ { id: 1, name: "Sarah Mitchell", business: "Luxe Beauty Bar", location: "New York, NY", review: "Our clients love booking through WhatsApp. We've seen a 45% increase in bookings and no-shows have dropped by 60%. Game-changer!", avatar: "S" }, { id: 2, name: "Maria Rodriguez", business: "Bella Vista Salon", location: "Miami, FL", review: "The Spanish language support is incredible. Our Latino clients finally feel truly understood. Revenue is up 35% since we started.", avatar: "M" }, { id: 3, name: "Jennifer Chen", business: "Glow Beauty Studio", location: "San Francisco, CA", review: "Setup took 10 minutes. Now we never miss late-night booking requests. The AI handles everything perfectly!", avatar: "J" }, ];

// --- LEGAL MODAL & CONTENT COMPONENTS ---

const LegalModal: React.FC<{ title: string; onClose: () => void; children: React.ReactNode }> = ({ title, onClose, children }) => (
  <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in-fast" onClick={onClose}>
    <div className="bg-white rounded-2xl shadow-2xl m-4 max-w-2xl w-full flex flex-col max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
      <div className="flex justify-between items-center p-6 border-b border-gray-200">
        <h2 className="text-2xl font-bold text-[#0e1116]">{title}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
          <X className="w-6 h-6" />
        </button>
      </div>
      <div className="p-6 space-y-4 overflow-y-auto text-gray-700 leading-relaxed">
        {children}
      </div>
      <div className="p-4 border-t border-gray-200 bg-gray-50 text-right">
        <button onClick={onClose} className="px-6 py-2 bg-[#d1ecc5] text-[#0e1116] rounded-lg font-semibold hover:bg-[#bde4b0] transition-all">
          Close
        </button>
      </div>
    </div>
  </div>
);

const PrivacyPolicyContent: React.FC = () => (
  <>
    <p className="font-semibold">Last Updated: June 12, 2025</p>
    <p>Eat Sleep Shop Repeat, LLC. ("us", "we", or "our") operates the Claxis website (the "Service"). This page informs you of our policies regarding the collection, use, and disclosure of personal data when you use our Service.</p>
    
    <h3 className="text-xl font-bold pt-4">1. Information Collection and Use</h3>
    <p>For a better experience while using our Service, particularly the waitlist form, we may require you to provide us with certain personally identifiable information, including but not limited to your email address. The information that we collect will be used to contact you with updates about Claxis, including its launch and related news.</p>

    <h3 className="text-xl font-bold pt-4">2. Third-Party Services</h3>
    <p>We use third-party services like Formspark for form submissions and Vercel/Netlify for hosting. These third parties have access to your Personal Information only to perform these tasks on our behalf and are obligated not to disclose or use it for any other purpose.</p>

    <h3 className="text-xl font-bold pt-4">3. Data Security</h3>
    <p>We value your trust in providing us your Personal Information, thus we are striving to use commercially acceptable means of protecting it. But remember that no method of transmission over the internet, or method of electronic storage is 100% secure and reliable, and we cannot guarantee its absolute security.</p>

    <h3 className="text-xl font-bold pt-4">4. Your Data Protection Rights</h3>
    <p>You have the right to access, update, or delete the information we have on you. If you wish to be informed what Personal Data we hold about you and if you want it to be removed from our systems, please contact us.</p>
    
    <h3 className="text-xl font-bold pt-4">5. Contact Us</h3>
    <p>If you have any questions or suggestions about our Privacy Policy, do not hesitate to contact us at <a href="mailto:hello@getclaxis.com" className="text-blue-600 hover:underline">hello@getclaxis.com</a>.</p>
  </>
);

const TermsOfServiceContent: React.FC = () => (
  <>
    <p className="font-semibold">Last Updated: June 12, 2025</p>
    <p>Please read these Terms of Service ("Terms", "Terms of Service") carefully before using the Claxis website (the "Service") operated by Eat Sleep Shop Repeat, LLC. ("us", "we", or "our").</p>
    <p>Your access to and use of the Service is conditioned on your acceptance of and compliance with these Terms. These Terms apply to all visitors, users, and others who access or use the Service.</p>

    <h3 className="text-xl font-bold pt-4">1. The Service</h3>
    <p>Claxis provides a waitlist for an upcoming software-as-a-service platform for appointment booking. The Service is provided on an "AS IS" and "AS AVAILABLE" basis. Its features may change without notice before the official launch.</p>

    <h3 className="text-xl font-bold pt-4">2. Intellectual Property</h3>
    <p>The Service and its original content, features, and functionality are and will remain the exclusive property of Eat Sleep Shop Repeat, LLC. and its licensors. The Claxis name and logo are trademarks of Eat Sleep Shop Repeat, LLC.</p>

    <h3 className="text-xl font-bold pt-4">3. Limitation Of Liability</h3>
    <p>In no event shall Eat Sleep Shop Repeat, LLC., nor its directors, employees, partners, agents, suppliers, or affiliates, be liable for any indirect, incidental, special, consequential or punitive damages, including without limitation, loss of profits, data, use, goodwill, or other intangible losses, resulting from your access to or use of or inability to access or use the Service.</p>

    <h3 className="text-xl font-bold pt-4">4. Governing Law</h3>
    <p>These Terms shall be governed and construed in accordance with the laws of the State of Delaware, United States, without regard to its conflict of law provisions.</p>
    
    <h3 className="text-xl font-bold pt-4">5. Contact Us</h3>
    <p>If you have any questions about these Terms, please contact us at <a href="mailto:hello@getclaxis.com" className="text-blue-600 hover:underline">hello@getclaxis.com</a>.</p>
  </>
);


// --- MAIN APP COMPONENT ---
function App() {
  const [isWaitlistModalOpen, setIsWaitlistModalOpen] = useState(false);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  
  // Other existing states...
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [visibleMessages, setVisibleMessages] = useState<Message[]>([]);
  const [currentTestimonial, setCurrentTestimonial] = useState(0);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  // All existing useEffect hooks for animations remain unchanged...
  useEffect(() => { let messageIndex = 0; const timeouts: ReturnType<typeof setTimeout>[] = []; const showNextMessage = () => { if (messageIndex >= conversationScript.length) { timeouts.push(setTimeout(() => { setVisibleMessages([]); messageIndex = 0; showNextMessage(); }, 8000)); return; } const message = conversationScript[messageIndex]; setVisibleMessages(prev => [...prev.filter(m => !m.isTyping), message]); const delay = message.isTyping ? 1500 : (message.sender === 'user' ? 1000 : 2500); messageIndex++; timeouts.push(setTimeout(showNextMessage, delay)); }; timeouts.push(setTimeout(showNextMessage, 500)); return () => timeouts.forEach(clearTimeout); }, []);
  useEffect(() => { if (chatContainerRef.current) { chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight; } }, [visibleMessages]);
  useEffect(() => { const interval = setInterval(() => { setCurrentTestimonial(prev => (prev + 1) % testimonials.length); }, 5000); return () => clearInterval(interval); }, []);

  const handleOpenModal = (modal: 'privacy' | 'terms') => (e: React.MouseEvent) => {
    e.preventDefault();
    setActiveModal(modal);
  };
  
  return (
    <>
      {/* Waitlist Modal */}
      {isWaitlistModalOpen && <WaitlistModal onClose={() => setIsWaitlistModalOpen(false)} />}
      
      {/* Legal Policy Modal */}
      {activeModal && (
        <LegalModal title={activeModal === 'privacy' ? "Privacy Policy" : "Terms of Service"} onClose={() => setActiveModal(null)}>
          {activeModal === 'privacy' && <PrivacyPolicyContent />}
          {activeModal === 'terms' && <TermsOfServiceContent />}
        </LegalModal>
      )}

      {/* The rest of your landing page */}
      <div className="min-h-screen bg-gradient-to-b from-[#E9E5F3] to-[#F5F5F5] text-[#0e1116] font-sans overflow-x-hidden">
        <div className="bg-[#0e1116] text-white py-2 px-4 text-center text-sm"><p className="flex items-center justify-center gap-2"><Shield className="w-4 h-4" /> Built with the Official WhatsApp Business API</p></div>
        
        {/* --- ⭐️ HEADER UPDATED WITH LOGO & TEXT ⭐️ --- */}
        <header className="sticky top-0 z-50 bg-white/50 backdrop-blur-md border-b border-black/5">
          <div className="max-w-7xl mx-auto px-4 py-4">
            <div className="flex items-center justify-between">
              {/* This is the corrected logo and text block */}
              <a href="#" className="flex items-center space-x-3">
                <img src={claxisLogo} alt="Claxis Logo" className="h-10 w-auto" />
                <span className="text-2xl font-bold text-[#0e1116]">Claxis</span>
              </a>
              <nav className="hidden md:flex items-center space-x-8">
                <a href="#features" className="text-[#0e1116]/60 hover:text-[#0e1116] font-medium transition-colors">Features</a>
                <a href="#testimonials" className="text-[#0e1116]/60 hover:text-[#0e1116] font-medium transition-colors">Testimonials</a>
                <a href="#security" className="text-[#0e1116]/60 hover:text-[#0e1116] font-medium transition-colors">Security</a>
              </nav>
              <div className="hidden md:block">
                <button onClick={() => setIsWaitlistModalOpen(true)} className="px-6 py-2.5 bg-[#d1ecc5] hover:bg-[#bde4b0] text-[#0e1116] rounded-xl font-semibold shadow-md hover:shadow-lg transition-all transform hover:scale-105">Join Waitlist</button>
              </div>
              <button onClick={() => setMobileMenuOpen(!mobileMenuOpen)} className="md:hidden text-[#0e1116]">
                <span className="sr-only">Toggle menu</span>{mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
            {mobileMenuOpen && (
              <nav className="md:hidden mt-4 pb-4 space-y-4">
                <a href="#features" onClick={() => setMobileMenuOpen(false)} className="block text-[#0e1116]/80 hover:text-[#0e1116] font-medium">Features</a>
                <a href="#testimonials" onClick={() => setMobileMenuOpen(false)} className="block text-[#0e1116]/80 hover:text-[#0e1116] font-medium">Testimonials</a>
                <a href="#security" onClick={() => setMobileMenuOpen(false)} className="block text-[#0e1116]/80 hover:text-[#0e1116] font-medium">Security</a>
                <button onClick={() => { setIsWaitlistModalOpen(true); setMobileMenuOpen(false); }} className="block w-full text-center px-6 py-2.5 bg-[#d1ecc5] text-[#0e1116] rounded-xl font-semibold">Join Waitlist</button>
              </nav>
            )}
          </div>
        </header>

        <main>
        <section className="relative px-4 pt-16 pb-24 text-center"><div className="max-w-4xl mx-auto"><h1 className="text-5xl sm:text-7xl font-bold text-[#0e1116] leading-tight mb-6">Your clients book appointments<span className="block text-transparent bg-clip-text bg-gradient-to-r from-[#e6d3f4] to-[#f2bc8f]">the way they already text</span></h1><p className="text-xl sm:text-2xl text-[#0e1116]/70 mb-8 leading-relaxed">Transform your salon's WhatsApp into an intelligent booking assistant that works 24/7, speaks every language, and never misses an opportunity.</p><button onClick={() => setIsWaitlistModalOpen(true)} className="px-8 py-4 bg-[#d1ecc5] hover:bg-[#bde4b0] text-[#0e1116] rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all transform hover:scale-105 flex items-center justify-center space-x-2 mx-auto"><span>Join the Waitlist</span><ArrowRight className="w-5 h-5" /></button></div></section>
        <section className="px-4"><div className="relative max-w-6xl mx-auto"><div className="absolute inset-0 bg-gradient-to-r from-[#e6d3f4]/30 to-[#d1ecc5]/30 rounded-3xl blur-3xl opacity-50"></div><div className="relative bg-white/60 backdrop-blur-sm rounded-3xl shadow-2xl p-8 border border-black/5"><div className="grid lg:grid-cols-2 gap-12 items-start"><div className="space-y-4"><div className="flex items-center space-x-3 mb-6"><div className="w-12 h-12 bg-[#25D366] rounded-full flex items-center justify-center shadow-lg"><MessageCircle className="w-7 h-7 text-white" /></div><div><h3 className="font-semibold text-[#0e1116]">Bella Vista Salon</h3><p className="text-sm text-[#0e1116]/60">online</p></div></div><div ref={chatContainerRef} className="space-y-4 h-[500px] overflow-y-auto pr-4 bg-[#e9e5f3]/30 p-4 rounded-xl border border-black/5">{visibleMessages.map((msg) => (<div key={msg.id} className={`flex items-end gap-2 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>{msg.sender === 'user' ? (<div className="bg-white rounded-2xl rounded-br-lg p-3 max-w-xs animate-slide-in-right shadow-sm border border-black/5"><div className="text-sm text-[#0e1116]">{msg.content}</div></div>) : (<div className={`bg-[#d1ecc5] rounded-2xl ${msg.isTyping ? 'p-3' : 'p-3 rounded-bl-lg'} max-w-xs text-[#0e1116] animate-slide-in-left shadow-sm`}>{msg.isTyping ? (<div className="flex items-center space-x-1.5"><span className="w-2 h-2 bg-black/30 rounded-full animate-bounce-short"></span><span className="w-2 h-2 bg-black/30 rounded-full animate-bounce-short [animation-delay:0.2s]"></span><span className="w-2 h-2 bg-black/30 rounded-full animate-bounce-short [animation-delay:0.4s]"></span></div>) : <div className="text-sm">{msg.content}</div>}</div>)}</div>))}</div></div><div className="space-y-6 pt-2"><div className="flex items-center space-x-3 mb-6"><div className="w-10 h-10 bg-white/80 rounded-xl flex items-center justify-center border border-black/5"><TrendingUp className="w-6 h-6 text-[#0e1116]/80" /></div><h3 className="font-semibold text-[#0e1116]">Real-Time Salon Dashboard</h3></div><div className="grid grid-cols-2 gap-4 mb-6"><div className="bg-white/70 rounded-xl p-4 border border-black/5"><div className="flex items-center justify-between mb-2"><Calendar className="w-5 h-5 text-[#0e1116]/50" /><span className="text-xs text-green-600 font-medium">+45%</span></div><p className="text-2xl font-bold text-[#0e1116]">312</p><p className="text-xs text-[#0e1116]/60">Bookings This Month</p></div><div className="bg-white/70 rounded-xl p-4 border border-black/5"><div className="flex items-center justify-between mb-2"><DollarSign className="w-5 h-5 text-[#0e1116]/50" /><span className="text-xs text-green-600 font-medium">+35%</span></div><p className="text-2xl font-bold text-[#0e1116]">$51.2k</p><p className="text-xs text-[#0e1116]/60">Revenue MTD</p></div></div><div className="bg-white/70 rounded-2xl p-6 border border-black/5"><h4 className="font-medium text-[#0e1116] mb-4">Today's Schedule</h4><div className="space-y-2"><div className="flex items-center justify-between p-3 bg-white/50 rounded-lg border border-black/5"><div className="flex items-center space-x-3"><div className="w-2 h-8 bg-[#e6d3f4] rounded-full"></div><div><p className="text-sm font-medium text-[#0e1116]">Emma Thompson</p><p className="text-xs text-[#0e1116]/60">Highlights & Cut</p></div></div><span className="text-sm text-[#0e1116]/60">9:00 AM</span></div><div className="flex items-center justify-between p-3 bg-white/50 rounded-lg border border-black/5"><div className="flex items-center space-x-3"><div className="w-2 h-8 bg-[#f2bc8f] rounded-full"></div><div><p className="text-sm font-medium text-[#0e1116]">Jessica Martinez</p><p className="text-xs text-[#0e1116]/60">Color Touch-up</p></div></div><span className="text-sm text-[#0e1116]/60">11:30 AM</span></div><div className="flex items-center justify-between p-3 bg-[#d1ecc5]/50 rounded-lg border-2 border-[#d1ecc5] animate-pulse-soft"><div className="flex items-center space-x-3"><div className="w-2 h-8 bg-gradient-to-b from-[#d1ecc5] to-[#f2bc8f] rounded-full"></div><div><p className="text-sm font-medium text-[#0e1116]">New: Via WhatsApp</p><p className="text-xs text-[#0e1116]/60">Balayage</p></div></div><span className="text-sm text-[#0e1116]/80 font-medium">3:30 PM</span></div></div></div></div></div></div></div></section>
        <section id="features" className="px-4 py-20 bg-gradient-to-b from-[#F5F5F5] to-white"><div className="max-w-7xl mx-auto"><div className="text-center mb-16"><h2 className="text-4xl sm:text-5xl font-bold text-[#0e1116] mb-4">An assistant that never sleeps</h2><p className="text-xl text-[#0e1116]/70 max-w-3xl mx-auto">Meet clients where they are - on the messaging app they use every day.</p></div><div className="grid md:grid-cols-2 gap-8"><div className="bg-white rounded-2xl p-8 border border-black/5 shadow-sm"><div className="flex items-center space-x-3 mb-6"><div className="w-12 h-12 bg-[#d1ecc5] rounded-xl flex items-center justify-center"><HeartHandshake className="w-7 h-7 text-[#0e1116]" /></div><h3 className="text-2xl font-semibold text-[#0e1116]">For Your Clients</h3></div><div className="space-y-5"><div className="flex items-start space-x-4"><div className="w-6 h-6 bg-[#d1ecc5] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><CheckCircle className="w-4 h-4 text-[#0e1116]" /></div><div><h4 className="font-medium text-[#0e1116] mb-1">Zero-Friction Booking</h4><p className="text-[#0e1116]/70">No apps to download, no passwords to remember.</p></div></div><div className="flex items-start space-x-4"><div className="w-6 h-6 bg-[#d1ecc5] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><CheckCircle className="w-4 h-4 text-[#0e1116]" /></div><div><h4 className="font-medium text-[#0e1116] mb-1">Book in Any Language</h4><p className="text-[#0e1116]/70">Serve your entire community with multilingual support.</p></div></div><div className="flex items-start space-x-4"><div className="w-6 h-6 bg-[#d1ecc5] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><CheckCircle className="w-4 h-4 text-[#0e1116]" /></div><div><h4 className="font-medium text-[#0e1116] mb-1">Instant Confirmations</h4><p className="text-[#0e1116]/70">Get booking confirmation in seconds, even at 2 AM.</p></div></div></div></div><div className="bg-white rounded-2xl p-8 border border-black/5 shadow-sm"><div className="flex items-center space-x-3 mb-6"><div className="w-12 h-12 bg-[#d1ecc5] rounded-xl flex items-center justify-center"><TrendingUp className="w-7 h-7 text-[#0e1116]" /></div><h3 className="text-2xl font-semibold text-[#0e1116]">For Your Business</h3></div><div className="space-y-5"><div className="flex items-start space-x-4"><div className="w-6 h-6 bg-[#d1ecc5] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><CheckCircle className="w-4 h-4 text-[#0e1116]" /></div><div><h4 className="font-medium text-[#0e1116] mb-1">24/7 Booking Coverage</h4><p className="text-[#0e1116]/70">Never lose a booking to voicemail again.</p></div></div><div className="flex items-start space-x-4"><div className="w-6 h-6 bg-[#d1ecc5] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><CheckCircle className="w-4 h-4 text-[#0e1116]" /></div><div><h4 className="font-medium text-[#0e1116] mb-1">60% Fewer No-Shows</h4><p className="text-[#0e1116]/70">WhatsApp reminders have 5x higher engagement.</p></div></div><div className="flex items-start space-x-4"><div className="w-6 h-6 bg-[#d1ecc5] rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"><CheckCircle className="w-4 h-4 text-[#0e1116]" /></div><div><h4 className="font-medium text-[#0e1116] mb-1">Human Handoff</h4><p className="text-[#0e1116]/70">Seamlessly escalate complex requests when needed.</p></div></div></div></div></div></div></section>
        <section id="testimonials" className="px-4 py-20 bg-white"><div className="max-w-4xl mx-auto text-center"><h2 className="text-4xl font-bold text-[#0e1116] mb-4">Trusted by America's leading salons</h2><div className="relative bg-gradient-to-br from-[#e9e5f3] to-white rounded-2xl p-8 md:p-12 mt-12 border border-black/5 shadow-lg overflow-hidden"><div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-[#d1ecc5]/20 to-[#f2bc8f]/20 rounded-full blur-3xl"></div><div className="relative transition-opacity duration-500" key={testimonials[currentTestimonial].id}><div className="flex items-center justify-center space-x-1 mb-6">{[...Array(5)].map((_, i) => <Star key={i} className="w-6 h-6 text-yellow-400 fill-yellow-400" />)}</div><blockquote className="text-2xl font-medium text-[#0e1116] mb-6 leading-relaxed">"{testimonials[currentTestimonial].review}"</blockquote><div className="flex items-center justify-center space-x-4"><div className="w-12 h-12 bg-gradient-to-br from-[#e6d3f4] to-[#f2bc8f] rounded-full flex items-center justify-center text-white font-bold text-lg">{testimonials[currentTestimonial].avatar}</div><div><p className="font-semibold text-[#0e1116]">{testimonials[currentTestimonial].name}</p><p className="text-[#0e1116]/70">{testimonials[currentTestimonial].business} • {testimonials[currentTestimonial].location}</p></div></div></div></div></div></section>
        <section id="security" className="px-4 py-20 bg-white"><div className="max-w-7xl mx-auto text-center"><h2 className="text-4xl font-bold text-[#0e1116] mb-4">Enterprise security, salon simplicity</h2><div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 mt-16"><div className="text-center"><div className="w-16 h-16 bg-[#25D366]/10 rounded-2xl flex items-center justify-center mx-auto mb-4"><MessageCircle className="w-8 h-8 text-[#25D366]" /></div><h3 className="font-semibold text-[#0e1116] mb-2">Powered by the Meta Cloud API</h3><p className="text-[#0e1116]/60 text-sm">Built with WhatsApp Cloud API for maximum reliability</p></div><div className="text-center"><div className="w-16 h-16 bg-[#d1ecc5]/20 rounded-2xl flex items-center justify-center mx-auto mb-4"><Shield className="w-8 h-8 text-[#0e1116]" /></div><h3 className="font-semibold text-[#0e1116] mb-2">CCPA & GDPR Ready</h3><p className="text-[#0e1116]/60 text-sm">Full compliance with US and EU privacy laws</p></div><div className="text-center"><div className="w-16 h-16 bg-[#e6d3f4]/20 rounded-2xl flex items-center justify-center mx-auto mb-4"><Lock className="w-8 h-8 text-[#0e1116]" /></div><h3 className="font-semibold text-[#0e1116] mb-2">256-bit Encryption</h3><p className="text-[#0e1116]/60 text-sm">End-to-end encryption for all conversations</p></div><div className="text-center"><div className="w-16 h-16 bg-[#f2bc8f]/20 rounded-2xl flex items-center justify-center mx-auto mb-4"><Award className="w-8 h-8 text-[#0e1116]" /></div><h3 className="font-semibold text-[#0e1116] mb-2">SOC 2 Type II</h3><p className="text-[#0e1116]/60 text-sm">Independently audited for security and compliance</p></div></div></div></section>
        <section className="px-4 py-20 bg-gradient-to-b from-white to-[#F5F5F5]"><div className="max-w-3xl mx-auto text-center"><h2 className="text-4xl sm:text-5xl font-bold text-[#0e1116] mb-6">Stop losing clients to voicemail.</h2><p className="text-xl text-[#0e1116]/70 mb-8">Join the waitlist to be the first to know when we launch in Q2 2025.</p><button onClick={() => setIsWaitlistModalOpen(true)} className="px-8 py-4 bg-[#d1ecc5] hover:bg-[#bde4b0] text-[#0e1116] rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transition-all transform hover:scale-105 flex items-center justify-center space-x-2 mx-auto"><span>Get Early Access</span><ArrowRight className="w-5 h-5" /></button></div></section>
        </main>
        
        {/* --- ⭐️ FOOTER UPDATED WITH LOGO & TEXT ⭐️ --- */}
        <footer className="px-4 py-16 bg-[#0e1116] text-white">
          <div className="max-w-6xl mx-auto">
              <div className="grid md:grid-cols-3 gap-8 mb-12">
                  <div className="md:col-span-2">
                      <div className="flex items-center space-x-3 mb-4">
                        <img src={claxisLogo} alt="Claxis Logo" className="h-10 w-auto" />
                        <span className="text-2xl font-bold">Claxis</span>
                      </div>
                      <p className="text-white/60 mb-6 max-w-md">
                          The WhatsApp-native booking platform built for America's beauty businesses.
                      </p>
                      <div className="space-y-2 text-white/60">
                          <div className="flex items-center space-x-2">
                              <Building className="w-4 h-4" />
                              <span className="text-sm">Eat Sleep Shop Repeat, LLC,</span>
                              <span className="text-sm">30 North Gould Street Ste N, Sheridan, 82801, WY</span>
                          </div>
                          
                          <div className="flex items-center space-x-2">
                              <Mail className="w-4 h-4" />
                              <a href="mailto:hello@getclaxis.com" className="text-sm hover:text-white transition-colors">
                                  hello@getclaxis.com
                              </a>
                          </div>
                          <div className="flex items-center space-x-2">
                              <Phone className="w-4 h-4" />
                              <span className="text-sm">+905433521189</span>
                          </div>
                      </div>
                  </div>
                  <div>
                      <h3 className="font-semibold mb-4">Company</h3>
                      <ul className="space-y-2 text-white/60">
                          <li><a href="#features" className="hover:text-white transition-colors">Features</a></li>
                          <li><a href="#testimonials" className="hover:text-white transition-colors">Testimonials</a></li>
                          <li><a href="#security" className="hover:text-white transition-colors">Security</a></li>
                      </ul>
                  </div>
              </div>
              
              <div className="border-t border-white/10 pt-8">
                  <div className="text-xs text-white/40 mb-6 max-w-3xl">
                      <p className="font-bold mb-2">Disclaimer:</p>
                      <p>
                          Claxis is an independent product developed by Eat Sleep Shop Repeat, LLC. It is not affiliated with, endorsed, or sponsored by Meta Platforms, Inc. or its subsidiary WhatsApp. The service utilizes the official WhatsApp Business Platform API to function, but all branding, features, and services are provided solely by Eat Sleep Shop Repeat, LLC.
                      </p>
                  </div>
                  
                  <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
                      <div className="text-white/40 text-sm">
                          © 2025 Eat Sleep Shop Repeat, LLC. All rights reserved.
                      </div>
                      <div className="flex space-x-6 text-sm">
                          <a href="#privacy" onClick={handleOpenModal('privacy')} className="text-white/60 hover:text-white transition-colors cursor-pointer">Privacy Policy</a>
                          <a href="#terms" onClick={handleOpenModal('terms')} className="text-white/60 hover:text-white transition-colors cursor-pointer">Terms of Service</a>
                      </div>
                  </div>
              </div>
          </div>
        </footer>
      </div>
    </>
  );
}

const WaitlistModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
    const [email, setEmail] = useState('');
    const [isValid, setIsValid] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
  
    const emailRegex = /^[a-zA-Z0-9._-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;
  
    useEffect(() => {
      setIsValid(emailRegex.test(email));
    }, [email]);
  
    const handleSubmit = () => {
      if (isValid) {
        setIsSubmitting(true);
      }
    };
  
    return (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-fade-in-fast">
        <div className="bg-white rounded-2xl shadow-2xl p-8 m-4 max-w-md w-full relative">
          <button onClick={onClose} className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-6 h-6" />
          </button>
          <h2 className="text-2xl font-bold text-[#0e1116] mb-2">Join the Priority Waitlist</h2>
          <p className="text-[#0e1116]/70 mb-6">Launching in Q2 2025. Be the first to get access.</p>
          
          <form
            action="https://submit-form.com/bEU0W6M8g"
            method="POST"
            onSubmit={handleSubmit}
          >
            <input type="hidden" name="_redirect" value="https://getclaxis.com/thank-you" /> 
            <input type="hidden" name="_error" value="https://your-domain.com/error" />
  
            <input
              type="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your business email"
              required
              className="w-full px-5 py-3 rounded-lg border-2 bg-[#e9e5f3]/40 text-[#0e1116] placeholder-[#0e1116]/50 focus:outline-none transition-all disabled:opacity-50 focus:ring-2 focus:ring-[#d1ecc5] border-transparent"
            />
            {!isValid && email.length > 0 && (
              <p className="text-red-500 text-sm mt-1 animate-fade-in-fast">Please enter a valid email address.</p>
            )}
  
            <button
              type="submit"
              disabled={!isValid || isSubmitting}
              className="w-full mt-3 px-6 py-3 bg-[#d1ecc5] text-[#0e1116] rounded-lg font-semibold text-lg hover:bg-[#bde4b0] transition-all flex items-center justify-center space-x-2 disabled:opacity-50 disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              {isSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Join the Waitlist'}
            </button>
          </form>
        </div>
      </div>
    );
  };

export default App;