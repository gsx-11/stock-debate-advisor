import React from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from '../components/Header';
import { Footer } from '../components/Footer';
import { ChatbotWidget } from '../components/ChatbotWidget';
import { Sidebar } from '../components/Sidebar';

export const MainLayout: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground dark:bg-slate-950">
      {/* Header with user profile, notifications, settings */}
      <Header />
      
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar Navigation */}
        <Sidebar />
        
        {/* Main Content */}
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8 lg:px-12 bg-gradient-to-br from-background/50 via-transparent to-transparent dark:from-slate-950/50">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
      
      <Footer />
      <ChatbotWidget />
    </div>
  );
};


