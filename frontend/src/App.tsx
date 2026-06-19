import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import Layout, { ToastProvider, WebSocketProgressProvider } from '@/components/Layout';
import './i18n';

const Dashboard = lazy(() => import('@/pages/Dashboard'));
const Channels = lazy(() => import('@/pages/Channels'));
const Jobs = lazy(() => import('@/pages/Jobs'));
const Developers = lazy(() => import('@/pages/Developers'));
const Messages = lazy(() => import('@/pages/Messages'));
const TelegramAccounts = lazy(() => import('@/pages/TelegramAccounts'));
const Websites = lazy(() => import('@/pages/Websites'));
const Autonomous = lazy(() => import('@/pages/Autonomous'));

function App() {
  return (
    <Router>
      <WebSocketProgressProvider>
        <ToastProvider>
          <Layout>
            <Suspense fallback={<div className="flex items-center justify-center h-screen">Loading...</div>}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/channels" element={<Channels />} />
                <Route path="/jobs" element={<Jobs />} />
                <Route path="/developers" element={<Developers />} />
                <Route path="/messages" element={<Messages />} />
                <Route path="/telegram-accounts" element={<TelegramAccounts />} />
                <Route path="/websites" element={<Websites />} />
                <Route path="/autonomous" element={<Autonomous />} />
              </Routes>
            </Suspense>
          </Layout>
        </ToastProvider>
      </WebSocketProgressProvider>
    </Router>
  );
}

export default App;
