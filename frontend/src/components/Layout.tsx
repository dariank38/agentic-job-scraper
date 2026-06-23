import { Link, useLocation } from 'react-router-dom';
import { useState, createContext, useContext, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import Footer from '@/components/Footer';
import { LanguageSwitcher } from '@/components/LanguageSwitcher';
import type { ProgressUpdate } from '@/hooks/useWebSocket';
import api from '@/services/api';
import {
  LayoutDashboard,
  Radio,
  MessageSquare,
  Briefcase,
  Code2,
  Menu,
  Zap,
  Globe,
  Bot,
  Settings2,
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
  currentAnalyzingMessage: Record<string, { message_id?: number; message_text: string; message_preview: string }>;
  statsUpdate: { total_channels: number; total_messages: number; total_jobs: number; total_developers: number } | null;
  cronStatus: { running: boolean } | null;
  listenerStatus: { running: boolean; account_id?: number } | null;
  channelUpdates: Array<{ id: number; username: string; is_listened: number; telegram_account_id: number | null }> | null;
  resumeGenerating: { job_id: number; job_title: string } | null;
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
  const [currentAnalyzingMessage, setCurrentAnalyzingMessage] = useState<Record<string, { message_id?: number; message_text: string; message_preview: string }>>({});
  const [statsUpdate, setStatsUpdate] = useState<{ total_channels: number; total_messages: number; total_jobs: number; total_developers: number } | null>(null);
  const [cronStatus, setCronStatus] = useState<{ running: boolean } | null>(null);
  const [listenerStatus, setListenerStatus] = useState<{ running: boolean; account_id?: number } | null>(null);
  const [channelUpdates, setChannelUpdates] = useState<Array<{ id: number; username: string; is_listened: number; telegram_account_id: number | null }> | null>(null);
  const [resumeGenerating, setResumeGenerating] = useState<{ job_id: number; job_title: string } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastNotificationRef = useRef<Record<string, number>>({});

  const requestStop = (channelId: number, channelUsername: string) => {
    setStoppingChannels(prev => ({ ...prev, [channelId]: true, [channelUsername]: true }));
  };

  // Request notification permission on mount
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const showNotification = (title: string, body: string) => {
    if ('Notification' in window && Notification.permission === 'granted') {
      const now = Date.now();
      const key = `${title}:${body}`;
      // Debounce: don't show same notification within 5 seconds
      if (lastNotificationRef.current[key] && now - lastNotificationRef.current[key] < 5000) {
        return;
      }
      lastNotificationRef.current[key] = now;
      new Notification(title, { body, icon: '/favicon.ico' });
    }
  };

  // Initial poll for operations on mount (for page refresh scenario)
  useEffect(() => {
    const pollOperations = async () => {
      try {
        const data = await api.getOperations();
        if (data.operations && data.operations.length > 0) {
          // Build operations state from running database operations (exclude bulk operations and website operations)
          const newOperations: Record<string, { type: string; status: string }> = {};
          data.operations.forEach((op: any) => {
            if (op.status === 'running' && op.channel_username && !op.bulk_operation_id && op.channel_id) {
              const opType = op.operation_type === 'analyze' ? 'analyze' : 'fetch';
              newOperations[op.channel_username] = { type: opType, status: 'running' };
            }
          });
          setOperations(newOperations);

          // Update bulk operations from API
          if (data.bulk_operations && data.bulk_operations.length > 0) {
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
          setOperations({});
          setBulkOperations([]);
          setChannelProgress({});
        }
      } catch (e) {
        // Silently ignore polling errors
      }
    };

    // Initial poll only (no interval - WebSocket handles real-time updates)
    pollOperations();
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

  // Fetch current analyzing state on mount (for page refresh scenario)
  useEffect(() => {
    const fetchCurrentAnalyzing = async () => {
      try {
        const data = await api.getCurrentAnalyzing();
        if (data.operations && data.operations.length > 0) {
          // For each running operation, set a placeholder analyzing message
          const analyzingState: Record<string, { message_id?: number; message_text: string; message_preview: string }> = {};
          data.operations.forEach((op: any) => {
            if (op.status === 'running' && op.channel_username) {
              analyzingState[op.channel_username] = {
                message_text: '',
                message_preview: `Analyzing ${op.analyzed}/${op.total} messages...`,
              };
            }
          });
          setCurrentAnalyzingMessage(analyzingState);
        }
      } catch (e) {
        // Silently ignore errors
      }
    };
    fetchCurrentAnalyzing();
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
        const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const wsUrl = import.meta.env.VITE_WS_BASE_URL || 
          `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${isLocalhost ? `${window.location.hostname}:8000` : window.location.host}/ws/progress`;
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as ProgressUpdate;
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
            } else if (channel && data.type === 'analyzing_message') {
              setCurrentAnalyzingMessage(prev => ({
                ...prev,
                [channel]: {
                  message_id: data.message_id,
                  message_text: data.message_text || "",
                  message_preview: data.message_preview || ""
                }
              }));
              // Update progress counter immediately when a message starts (not just when it finishes)
              if (data.total_messages || data.total) {
                setChannelProgress(prev => ({
                  ...prev,
                  [channel]: {
                    analyzed: data.analyzed ?? prev[channel]?.analyzed ?? 0,
                    total: data.total_messages || data.total || prev[channel]?.total || 0,
                  }
                }));
              }
            } else if (channel && data.type === 'analyze_progress') {
              setChannelProgress(prev => ({
                ...prev,
                [channel]: {
                  analyzed: data.analyzed || 0,
                  total: data.total_messages || data.total || 0,
                }
              }));
              // Update token usage (handle both nested tokens object and top-level fields)
              if (data.tokens) {
                setTokenUsage(prev => ({
                  ...prev,
                  [channel]: data.tokens!
                }));
              } else if (data.input_tokens !== undefined || data.output_tokens !== undefined) {
                setTokenUsage(prev => ({
                  ...prev,
                  [channel]: {
                    input: data.input_tokens || 0,
                    output: data.output_tokens || 0,
                    total: data.total_tokens || 0,
                  }
                }));
              }
              // Update message results (cap at 100 per channel to prevent memory leak)
              if (data.message_results && data.message_results.length > 0) {
                setMessageResults(prev => ({
                  ...prev,
                  [channel]: [...(prev[channel] || []), ...data.message_results!].slice(-100)
                }));
                // Show notifications for job/developer discoveries
                data.message_results.forEach((result: any) => {
                  if (result.category === 'job_posting') {
                    const title = result.title || 'Unknown';
                    const company = result.company || 'Unknown';
                    showNotification('New Job Found', `${title} at ${company} from ${channel}`);
                  } else if (result.category === 'personal_info') {
                    const name = result.name || 'Unknown';
                    showNotification('New Developer Found', `${name} from ${channel}`);
                  }
                });
              }
            } else if (channel && (data.type === 'analyze_complete' || data.type === 'fetch_complete' || data.type === 'error')) {
              // Show notification for analysis completion
              if (data.type === 'analyze_complete') {
                showNotification('Analysis Complete', `Finished analyzing ${channel}`);
              } else if (data.type === 'error') {
                showNotification('Analysis Error', `Error analyzing ${channel}`);
              }
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
              // Clear current analyzing message for completed channel
              setCurrentAnalyzingMessage(prev => {
                const newMessages = { ...prev };
                delete newMessages[channel];
                return newMessages;
              });
            } else if (data.type === 'stats_update') {
              setStatsUpdate({
                total_channels: data.total_channels || 0,
                total_messages: data.total_messages || 0,
                total_jobs: data.total_jobs || 0,
                total_developers: data.total_developers || 0
              });
            } else if (data.type === 'cron_status') {
              setCronStatus({ running: data.running || false });
            } else if (data.type === 'listener_status') {
              setListenerStatus({ running: data.running || false, account_id: data.account_id });
            } else if (data.type === 'resume_generating') {
              setResumeGenerating({ job_id: data.job_id ?? 0, job_title: data.job_title || '' });
            } else if (data.type === 'resume_complete') {
              setResumeGenerating(null);
            } else if (data.type === 'channel_update') {
              setChannelUpdates(data.channels || []);
            } else if (data.type === 'bulk_fetch_start') {
              // Handle bulk fetch start
              setBulkOperations(prev => [
                ...prev,
                { id: String(data.operation_id), operation_type: 'fetch-all', status: 'running', channels: [] }
              ]);
            } else if (data.type === 'bulk_fetch_progress') {
              // Handle bulk fetch progress
              setBulkOperations(prev => prev.map(op => 
                op.id === String(data.operation_id) 
                  ? { ...op, status: 'running' }
                  : op
              ));
            } else if (data.type === 'bulk_fetch_complete' || data.type === 'bulk_fetch_stopped') {
              // Handle bulk fetch completion or stop
              setBulkOperations(prev => prev.filter(op => op.id !== String(data.operation_id)));
              if (data.type === 'bulk_fetch_complete') {
                showNotification('Bulk Fetch Complete', `Fetched ${data.total_new_messages} new messages`);
              }
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
    <WebSocketProgressContext.Provider value={{ progress, isConnected, channelProgress, operations, bulkOperations, stoppingChannels, tokenUsage, messageResults, currentAnalyzingMessage, statsUpdate, cronStatus, listenerStatus, channelUpdates, resumeGenerating, requestStop }}>
      {children}
    </WebSocketProgressContext.Provider>
  );
};

const Layout = ({ children }: { children: React.ReactNode }) => {
  const { t } = useTranslation();
  const location = useLocation();
  const [sheetOpen, setSheetOpen] = useState(false);

  const navLinks = [
    { path: '/', label: t('nav.dashboard'), icon: LayoutDashboard },
    { path: '/jobs', label: t('nav.jobs'), icon: Briefcase },
    { path: '/developers', label: t('nav.developers'), icon: Code2 },
    { path: '/messages', label: t('nav.messages'), icon: MessageSquare },
    { path: '/channels', label: t('nav.channels'), icon: Radio },
    { path: '/websites', label: t('nav.websites'), icon: Globe },
    { path: '/telegram-accounts', label: t('nav.telegramAccounts'), icon: Radio },
    { path: '/settings', label: 'Settings', icon: Settings2 },
    { path: '/autonomous', label: 'Autonomous', icon: Bot },
  ];

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
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {navLinks.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                title={label}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-sm font-medium no-underline transition-colors ${
                  isActive(path)
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                }`}
              >
                <Icon size={14} />
                <span className="hidden xl:inline">{label}</span>
              </Link>
            ))}
            <LanguageSwitcher />
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
                  <div className="border-t pt-3 mt-3">
                    <LanguageSwitcher />
                  </div>
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
