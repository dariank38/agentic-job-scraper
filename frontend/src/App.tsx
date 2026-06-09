import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout, { ToastProvider, WebSocketProgressProvider } from '@/components/Layout';
import Dashboard from '@/pages/Dashboard';
import Channels from '@/pages/Channels';
import Jobs from '@/pages/Jobs';
import Developers from '@/pages/Developers';
import Messages from '@/pages/Messages';
import TelegramAccounts from '@/pages/TelegramAccounts';
import Websites from '@/pages/Websites';

function App() {
  return (
    <Router>
      <WebSocketProgressProvider>
        <ToastProvider>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/channels" element={<Channels />} />
              <Route path="/jobs" element={<Jobs />} />
              <Route path="/developers" element={<Developers />} />
              <Route path="/messages" element={<Messages />} />
              <Route path="/telegram-accounts" element={<TelegramAccounts />} />
              <Route path="/websites" element={<Websites />} />
            </Routes>
          </Layout>
        </ToastProvider>
      </WebSocketProgressProvider>
    </Router>
  );
}

export default App;
