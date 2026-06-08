import { Link, useLocation } from 'react-router-dom';
import { useState, createContext, useContext, useEffect, useRef } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import Footer from '@/components/Footer';
import type { ProgressUpdate } from '@/hooks/useWebSocket';
import {
  LayoutDashboard,
  Radio,
  MessageSquare,
  Briefcase,
  Code2,
  Menu,
  Zap,
} from 'lucide-react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  showToast: (type: ToastType, message: string) => void;
}

const ToastContext = createContext<ToastContextType | null>(null);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
};

interface WebSocketProgressContextType {
  progress: ProgressUpdate | null;
  isConnected: boolean;
  channelProgress: Record<string, { analyzed: number; total: number }>;
  operations: Record<string, { type: string; status: string }>;
  bulkOperations: Array<{ id: string; operation_type: string; status: string; channels: number[] }>;
  stoppingChannels: Record<string, boolean>;
  tokenUsage: Record<string, { input: number; output: number; total: number }>;
  messageResults: Record<string, any[]>;
  requestStop: (channelId: number, channelUsername: string) => void;
}

const WebSocketProgressContext = createContext<WebSocketProgressContextType | null>(null);

export const useWebSocketProgress = () => {
  const context = useContext(WebSocketProgressContext);
  if (!context) throw new Error('useWebSocketProgress must be used within WebSocketProgressProvider');
  return context;
};

const toastVariants: Record<ToastType, string> = {
  success: 'bg-green-50 border-green-200 text-green-800',
  error: 'bg-red-50 border-red-200 text-red-800',
  info: 'bg-blue-50 border-blue-200 text-blue-800',
  warning: 'bg-yellow-50 border-yellow-200 text-yellow-800',
};

const ToastProvider = ({ children }: { children: React.ReactNode }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = (type: ToastType, message: string) => {
    const id = Date.now().toString();
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3500);
  };

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map(toast => (
          <div
            key={toast.id}
            className={`border rounded-lg px-4 py-3 shadow-lg min-w-[280px] text-sm font-medium animate-in slide-in-from-right-4 fade-in duration-200 pointer-events-auto ${toastVariants[toast.type]}`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

const WebSocketProgressProvider = ({ children }: { children: React.ReactNode }) => {
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const [channelProgress, setChannelProgress] = useState<Record<string, { analyzed: number; total: number }>>({});
  const [operations, setOperations] = useState<Record<string, { type: string; status: string }>>({});
  const [bulkOperations, setBulkOperations] = useState<Array<{ id: string; operation_type: string; status: string; channels: number[] }>>([]);
  const [stoppingChannels, setStoppingChannels] = useState<Record<string, boolean>>({});
  const [tokenUsage, setTokenUsage] = useState<Record<string, { input: number; output: number; total: number }>>({});
  const [messageResults, setMessageResults] = useState<Record<string, any[]>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  const requestStop = (channelId: number, channelUsername: string) => {
    setStoppingChannels(prev => ({ ...prev, [channelId]: true, [channelUsername]: true }));
  };

  // Poll operations API as fallback when WebSocket is disconnected
  useEffect(() => {
    const pollOperations = async () => {
      try {
        const api = (await import('../services/api')).default;
        const data = await api.getOperations();
        console.log(`[POLL] Operations: ${data.operations?.length || 0}, BulkOps: ${data.bulk_operations?.length || 0}`);
        if (data.operations && data.operations.length > 0) {
          data.operations.forEach((op: any) => {
            if (op.status === 'running') {
              console.log(`[POLL] Running: ${op.channel_username} | ${op.operation_type} | ${op.analyzed}/${op.total_messages}`);
            }
          });
          // Build operations state from running database operations
          const newOperations: Record<string, { type: string; status: string }> = {};
          data.operations.forEach((op: any) => {
            if (op.status === 'running' && op.channel_username) {
              const opType = op.operation_type === 'analyze' ? 'analyze' : 'fetch';
              newOperations[op.channel_username] = { type: opType, status: 'running' };
            }
          });
          setOperations(newOperations);

          // Update bulk operations from API
          if (data.bulk_operations && data.bulk_operations.length > 0) {
            console.log(`[POLL] BulkOps active:`, data.bulk_operations.map((b: any) => b.id));
            setBulkOperations(data.bulk_operations);
          } else {
            setBulkOperations([]);
          }

          // Update channel progress for running operations
          data.operations.forEach((op: any) => {
            if (op.status === 'running' && op.channel_username) {
              setChannelProgress(prev => ({
                ...prev,
                [op.channel_username]: {
                  analyzed: op.analyzed || 0,
                  total: op.total_messages || op.total || 0,
                }
              }));
            }
          });
        } else {
          // No running operations, clear all
          console.log('[POLL] No running operations, clearing state');
          setOperations({});
          setBulkOperations([]);
          setChannelProgress({});
        }
      } catch (e) {
        // Silently ignore polling errors
      }
    };

    // Initial poll
    pollOperations();

    // Set up polling interval (every 5 seconds)
    pollIntervalRef.current = window.setInterval(pollOperations, 5000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Restore progress from localStorage on mount
  useEffect(() => {
    const savedProgress = localStorage.getItem('ws_progress');
    if (savedProgress) {
      try {
        setProgress(JSON.parse(savedProgress));
      } catch (e) {
        // Ignore parse errors
      }
    }
    const savedChannelProgress = localStorage.getItem('ws_channel_progress');
    if (savedChannelProgress) {
      try {
        setChannelProgress(JSON.parse(savedChannelProgress));
      } catch (e) {
        // Ignore parse errors
      }
    }
  }, []);

  // Save progress to localStorage whenever it changes
  useEffect(() => {
    if (progress) {
      localStorage.setItem('ws_progress', JSON.stringify(progress));
    } else {
      localStorage.removeItem('ws_progress');
    }
  }, [progress]);

  // Save channel progress to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('ws_channel_progress', JSON.stringify(channelProgress));
  }, [channelProgress]);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const connect = () => {
      try {
        // Use environment variable or construct from current location for same-domain requests
        const wsUrl = import.meta.env.VITE_WS_BASE_URL || 
          `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/progress`;
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as ProgressUpdate;
            console.log(`[WS ${data.type}] Channel: ${data.channel || 'N/A'}`, data);
            setProgress(data);

            // Update channel progress and operations
            const channel = data.channel;
            if (channel && (data.type === 'analyze_start' || data.type === 'fetch_start')) {
              // Start operation
              const opType = data.type === 'analyze_start' ? 'analyze' : 'fetch';
              setOperations(prev => ({
                ...prev,
                [channel]: { type: opType, status: 'running' }
              }));
              setChannelProgress(prev => ({
                ...prev,
                [channel]: { analyzed: 0, total: 0 }
              }));
            } else if (channel && data.type === 'fetch_progress') {
              // Handle fetch progress updates
              setChannelProgress(prev => ({
                ...prev,
                [channel]: {
                  analyzed: data.processed || data.analyzed || 0,
                  total: data.total_messages || data.total || 0,
                }
              }));
            } else if (channel && data.type === 'analyze_progress') {
              setChannelProgress(prev => ({
                ...prev,
                [channel]: {
                  analyzed: data.analyzed || 0,
                  total: data.total_messages || data.total || 0,
                }
              }));
              // Update token usage
              if (data.tokens) {
                setTokenUsage(prev => ({
                  ...prev,
                  [channel]: data.tokens!
                }));
              }
              // Update message results
              if (data.message_results && data.message_results.length > 0) {
                setMessageResults(prev => ({
                  ...prev,
                  [channel]: [...(prev[channel] || []), ...data.message_results!]
                }));
              }
            } else if (channel && (data.type === 'analyze_complete' || data.type === 'fetch_complete' || data.type === 'error')) {
              // End operation - also clear stopping state
              setOperations(prev => {
                const newOps = { ...prev };
                delete newOps[channel];
                return newOps;
              });
              setChannelProgress(prev => {
                const newProgress = { ...prev };
                delete newProgress[channel];
                return newProgress;
              });
              setStoppingChannels(prev => {
                const newStopping = { ...prev };
                delete newStopping[channel];
                return newStopping;
              });
              // Clear token usage for completed channel
              setTokenUsage(prev => {
                const newTokens = { ...prev };
                delete newTokens[channel];
                return newTokens;
              });
              // Clear message results for completed channel
              setMessageResults(prev => {
                const newResults = { ...prev };
                delete newResults[channel];
                return newResults;
              });
            }
          } catch (e) {
            // Silently ignore parse errors
          }
        };

        ws.onerror = () => {
          setIsConnected(false);
        };

        ws.onclose = () => {
          setIsConnected(false);
          reconnectTimer = window.setTimeout(() => {
            connect();
          }, 5000);
        };
      } catch (e) {
        setIsConnected(false);
      }
    };

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  return (
    <WebSocketProgressContext.Provider value={{ progress, isConnected, channelProgress, operations, bulkOperations, stoppingChannels, tokenUsage, messageResults, requestStop }}>
      {children}
    </WebSocketProgressContext.Provider>
  );
};

const navLinks = [
  { path: '/', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/channels', label: 'Channels', icon: Radio },
  { path: '/messages', label: 'Messages', icon: MessageSquare },
  { path: '/jobs', label: 'Jobs', icon: Briefcase },
  { path: '/developers', label: 'Developers', icon: Code2 },
  { path: '/telegram-accounts', label: 'Telegram Accounts', icon: Radio },
];

const Layout = ({ children }: { children: React.ReactNode }) => {
  const location = useLocation();
  const [sheetOpen, setSheetOpen] = useState(false);

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <div className="min-h-screen bg-muted/40">
      {/* Header */}
      <header className="bg-background border-b sticky top-0 z-50">
        <div className="max-w-[1280px] mx-auto px-4 md:px-8 h-14 flex items-center justify-between gap-4">

          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 no-underline shrink-0">
            <div className="bg-primary text-primary-foreground w-8 h-8 rounded-lg flex items-center justify-center shadow-sm">
              <Zap size={15} strokeWidth={2.5} />
            </div>
            <span className="font-bold text-foreground tracking-tight">
              Job Scraper
            </span>
            <Badge variant="secondary" className="rounded-full text-[10px] px-1.5 py-0 h-4">
              Beta
            </Badge>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium no-underline transition-colors ${
                  isActive(path)
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >
                <Icon size={14} />
                {label}
              </Link>
            ))}
          </nav>

          {/* Mobile Menu — shadcn Sheet */}
          <div className="md:hidden">
            <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon">
                  <Menu size={20} />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0">
                <SheetHeader className="px-4 py-4 border-b">
                  <SheetTitle className="flex items-center gap-2">
                    <div className="bg-primary text-primary-foreground w-7 h-7 rounded-md flex items-center justify-center">
                      <Zap size={13} strokeWidth={2.5} />
                    </div>
                    Job Scraper
                  </SheetTitle>
                </SheetHeader>
                <nav className="flex flex-col p-3 gap-1">
                  {navLinks.map(({ path, label, icon: Icon }) => (
                    <Button
                      key={path}
                      asChild
                      variant={isActive(path) ? 'secondary' : 'ghost'}
                      className="justify-start gap-2 font-medium"
                      onClick={() => setSheetOpen(false)}
                    >
                      <Link to={path}>
                        <Icon size={15} />
                        {label}
                      </Link>
                    </Button>
                  ))}
                </nav>
              </SheetContent>
            </Sheet>
          </div>

        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1280px] mx-auto px-4 md:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
};

export default Layout;
export { ToastProvider, WebSocketProgressProvider };
