import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DailyJobsChart } from '@/components/DailyJobsChart';
import { DailyDevelopersChart } from '@/components/DailyDevelopersChart';
import { DailyJobsAppliedChart } from '@/components/DailyJobsAppliedChart';
import {
  MessageSquare,
  Clock,
  SkipForward,
  Radio,
  Briefcase,
  Users,
  CheckCircle2,
  Bot,
  Timer,
  RefreshCw,
  Play,
  Square,
  Zap,
  Calendar,
  MapPin,
  Mail,
  ExternalLink,
} from 'lucide-react';
import api from '@/services/api';
import type { Channel, Stats, WebsiteSource, Job, Developer, TelegramAccount } from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

const Dashboard = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [websiteSources, setWebsiteSources] = useState<WebsiteSource[]>([]);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const [cronRunning, setCronRunning] = useState(false);
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(30);
  const [bulkOperation, setBulkOperation] = useState<{ id: string; type: 'analyze-all' | 'fetch-analyze-all' } | null>(null);
  const [listenerRunning, setListenerRunning] = useState(false);
  const [listenerDialogOpen, setListenerDialogOpen] = useState(false);
  const [listenedChannels, setListenedChannels] = useState<string[]>([]);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [recentDevelopers, setRecentDevelopers] = useState<Developer[]>([]);
  const [telegramAccounts, setTelegramAccounts] = useState<TelegramAccount[]>([]);

  const { progress: wsProgress, channelProgress, operations, bulkOperations, requestStop, currentAnalyzingMessage } = useWebSocketProgress();

  useEffect(() => {
    if (wsProgress && (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error' || wsProgress.type === 'fetch_complete')) {
      loadData();
      loadRecentJobs();
      loadRecentDevelopers();
    }
  }, [wsProgress]);

  // Track which website sources are currently being analyzed via WS (keyed by source name)
  const wsSourceAnalyzing: Record<string, boolean> = {};
  websiteSources.forEach(s => {
    if (channelProgress[s.name]) wsSourceAnalyzing[s.name] = true;
  });
  const anyWebsiteAnalyzing = Object.keys(wsSourceAnalyzing).length > 0;

  // Derive effective bulk operation (local state or from context polling)
  const effectiveBulkOperation = bulkOperation || (bulkOperations.length > 0 ? {
    id: bulkOperations[0].id,
    type: bulkOperations[0].operation_type as 'analyze-all' | 'fetch-analyze-all'
  } : null);

  // Clear local bulkOperation when bulkOperations from context is empty
  useEffect(() => {
    if (bulkOperation && bulkOperations.length === 0 && Object.keys(operations).length === 0) {
      // Wait a moment to ensure operations are truly done, then clear bulk state
      const timer = setTimeout(() => {
        setBulkOperation(null);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [operations, bulkOperations, bulkOperation]);

  useEffect(() => {
    loadData();
    checkCronStatus();
    checkListenerStatus();
    loadRecentJobs();
    loadRecentDevelopers();
    const interval = setInterval(() => {
      loadData();
      checkCronStatus();
      checkListenerStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadRecentJobs = async () => {
    try {
      const data = await api.getJobs({ limit: 1, offset: 0 });
      setRecentJobs(data.jobs || []);
    } catch (e: any) {
      // Silently ignore errors
    }
  };

  const loadRecentDevelopers = async () => {
    try {
      const data = await api.getDevelopers({ limit: 1, offset: 0 });
      setRecentDevelopers(data.developers || []);
    } catch (e: any) {
      // Silently ignore errors
    }
  };

  const loadData = async () => {
    try {
      const [statsData, channelsData, sourcesData, accountsData] = await Promise.all([
        api.getStats(),
        api.getChannels({ limit: 1000 }), // Get all channels without pagination
        api.getWebsiteSources(),
        api.getTelegramAccounts(),
      ]);
      setStats(statsData);
      setChannels(channelsData.channels);
      setWebsiteSources(sourcesData.sources || []);
      setTelegramAccounts(accountsData);
    } catch (error) {
      // Silently ignore errors
    }
  };

  const withLoading = async <T,>(
    actionKey: string,
    fn: () => Promise<T>
  ): Promise<T> => {
    setLoadingActions(prev => new Set(prev).add(actionKey));
    try {
      return await fn();
    } finally {
      setLoadingActions(prev => {
        const next = new Set(prev);
        next.delete(actionKey);
        return next;
      });
    }
  };

  const checkCronStatus = async () => {
    try {
      const data = await api.getCronStatus();
      if (data.success) {
        setCronRunning(data.running);
      }
    } catch (error) {
      // Silently ignore cron status check errors
    }
  };

  // Check listener status across all accounts
  const checkListenerStatus = async () => {
    try {
      // Get all authenticated accounts
      const accounts = telegramAccounts.length > 0 ? telegramAccounts : await api.getTelegramAccounts();
      const authenticatedAccounts = accounts.filter((a: TelegramAccount) => a.is_authenticated);

      if (authenticatedAccounts.length === 0) {
        setListenerRunning(false);
        setListenedChannels([]);
        return;
      }

      // Check all accounts and merge listened channels
      const allListenedChannels: string[] = [];
      let anyRunning = false;

      for (const account of authenticatedAccounts) {
        try {
          const statusData = await api.getListenerStatus(account.id);
          if (statusData.running) {
            anyRunning = true;
            const channelsData = await api.getListenerChannels(account.id);
            if (channelsData.listening_to) {
              // Normalize usernames to include @ prefix
              const normalizedChannels = channelsData.listening_to.map((username: string) =>
                username.startsWith('@') ? username : `@${username}`
              );
              allListenedChannels.push(...normalizedChannels);
            }
          }
        } catch (e) {
          // Skip accounts that fail
        }
      }

      setListenerRunning(anyRunning);
      setListenedChannels([...new Set(allListenedChannels)]);
    } catch (e) {
      // Silently ignore
    }
  };

  const stopListener = async () => {
    try {
      const data = await api.stopListener();
      if (data.success) {
        showToast('success', t('dashboard.listenerStopped'));
        setListenerRunning(false);
        setListenedChannels([]);
      } else {
        showToast('error', data.error || t('dashboard.failedToStopListener'));
      }
    } catch (e: any) {
      showToast('error', `${t('dashboard.failedToStopListener')}: ${e.message}`);
    }
  };

  // Simple toggle listener for a single channel - uses channel's assigned account automatically
  const toggleChannelListener = async (channel: Channel) => {
    const actionKey = `listener-toggle-${channel.id}`;
    try {
      setLoadingActions(prev => new Set(prev).add(actionKey));

      const isListening = listenedChannels.includes(channel.username);
      const accountId = channel.telegram_account_id;

      if (isListening) {
        // Stop listening
        const data = await api.removeListenerChannels([channel.username], accountId);
        if (data.success) {
          setListenedChannels(data.listening_to || []);
        } else {
          showToast('error', data.error || t('dashboard.failedToStopListener'));
        }
      } else {
        // Add channel - backend will auto-start listener if needed
        const data = await api.addListenerChannels([channel.username], accountId);
        if (data.success) {
          setListenerRunning(true);
        } else {
          showToast('error', data.error || t('dashboard.failedToAddChannel'));
        }
        // Refresh listened channels list to get updated status
        await checkListenerStatus();
      }
    } catch (e: any) {
      showToast('error', `${t('dashboard.failedToToggleListener')}: ${e.message}`);
    } finally {
      setLoadingActions(prev => {
        const next = new Set(prev);
        next.delete(actionKey);
        return next;
      });
    }
  };

  const toggleCron = async () => {
    try {
      if (cronRunning) {
        const data = await api.stopCron();
        if (data.success) {
          setCronRunning(false);
          showToast('success', t('dashboard.cronStopped'));
        } else {
          showToast('error', `${t('common.error')}: ` + (data.message || t('common.unknown')));
        }
      } else {
        const data = await api.startCron();
        if (data.success) {
          setCronRunning(true);
          showToast('success', t('dashboard.cronStarted'));
        } else {
          showToast('error', `${t('common.error')}: ` + (data.message || t('common.unknown')));
        }
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const fetchAll = async () => {
    try {
      const data = await withLoading('fetch-all', () => api.fetchAll());
      if (data.success) {
        const total = data.results.reduce((s: number, r: any) => s + (r.new_messages || 0), 0);
        showToast('success', t('dashboard.fetchedAllMessages', { count: total }));
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const analyzeAll = async () => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }

      const data = await withLoading('analyze-all', () => api.analyzeAll());
      if (data.success) {
        if (data.operation_id) {
          setBulkOperation({ id: data.operation_id, type: 'analyze-all' });
        }
        showToast('success', t('dashboard.analysisStarted', { count: data.channels }));
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const cleanupOldMessages = async () => {
    if (!confirm(t('dashboard.deleteMessagesOlder', { days: cleanupDays }))) {
      return;
    }
    try {
      const data = await withLoading('cleanup', () => api.cleanupOldMessages(cleanupDays));
      if (data.success) {
        showToast('success', data.message || t('dashboard.deletedMessages', { count: data.deleted }));
        loadData();
        setCleanupDialogOpen(false);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.message || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const fetchAllWebsites = async () => {
    try {
      const data = await withLoading('fetch-all-ws', () => api.fetchAllWebsiteSources());
      if (data.success) {
        showToast('success', t('dashboard.fetchedAllMessages', { count: data.total_new ?? 0 }));
        loadData();
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const analyzeAllWebsites = async () => {
    try {
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }
      const data = await withLoading('analyze-all-ws', () => api.analyzeAllWebsiteSources());
      if (data.success) {
        showToast('success', data.message || t('dashboard.analysisStarted', { count: data.sources ?? 0 }));
        setTimeout(() => loadData(), 2000);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const stopAllWebsites = async () => {
    const activeSources = websiteSources.filter(s => wsSourceAnalyzing[s.name]);
    for (const source of activeSources) {
      try {
        requestStop(source.id, source.name);
        await api.stopWebsiteSource(source.id);
      } catch {}
    }
    showToast('success', t('dashboard.stopSignalSent'));
  };

  const stopBulkOperation = async () => {
    const targetBulkOp = bulkOperation || effectiveBulkOperation;
    if (!targetBulkOp) return;
    try {
      const data = await api.stopBulkOperation(targetBulkOp.id);
      if (data.success) {
        showToast('success', t('dashboard.stopBulkSignalSent'));
        setBulkOperation(null);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.message || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const statItems = [
    { icon: MessageSquare, value: stats?.total_messages ?? '-', label: t('dashboard.totalMessages'), color: 'text-cyan-600 bg-cyan-100' },
    { icon: Clock, value: stats?.pending_messages ?? '-', label: t('dashboard.pendingAnalysis'), color: 'text-yellow-600 bg-yellow-100' },
    { icon: SkipForward, value: stats?.skipped_messages ?? '-', label: t('dashboard.skipped'), color: 'text-gray-600 bg-gray-100' },
    { icon: Radio, value: stats?.total_channels ?? '-', label: t('dashboard.channels'), color: 'text-blue-600 bg-blue-100' },
    { icon: Briefcase, value: stats?.job_postings ?? '-', label: t('dashboard.jobPostings'), color: 'text-green-600 bg-green-100' },
    { icon: Users, value: stats?.developers ?? '-', label: t('dashboard.developers'), color: 'text-purple-600 bg-purple-100' },
    { icon: CheckCircle2, value: stats?.applications?.jobs?.total ?? '-', label: t('dashboard.jobsApplied'), color: 'text-orange-600 bg-orange-100' },
    { icon: Bot, value: stats?.ollama_available ? t('dashboard.online') : t('dashboard.offline'), label: t('dashboard.ollama'), color: stats?.ollama_available ? 'text-green-600 bg-green-100' : 'text-red-600 bg-red-100' },
  ];

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Sidebar Navigation */}
      <div className="w-full lg:w-72 shrink-0 space-y-4">
        {/* Quick Actions - Glassmorphism */}
        <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
          <CardHeader className="px-4 py-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Zap size={16} className="text-yellow-500" />
              {t('dashboard.quickActions')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-3">
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('dashboard.allChannels')}</p>
              <div className="flex gap-2">
                <Button
                  onClick={() => fetchAll()}
                  disabled={loadingActions.has('fetch-all') || Object.keys(operations).length > 0 || effectiveBulkOperation !== null}
                  size="sm"
                  className="flex-1 h-8"
                >
                  <RefreshCw size={12} className="mr-1" />
                  {t('dashboard.fetchAll')}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => analyzeAll()}
                  disabled={loadingActions.has('analyze-all') || Object.keys(operations).length > 0 || effectiveBulkOperation !== null}
                  size="sm"
                  className="flex-1 h-8"
                >
                  <Bot size={12} className="mr-1" />
                  {t('dashboard.analyzeAll')}
                </Button>
              </div>
              {effectiveBulkOperation && (
                <Button
                  variant="destructive"
                  onClick={() => stopBulkOperation()}
                  size="sm"
                  className="w-full h-7 text-xs"
                >
                  <Square size={10} className="mr-1" />
                  {effectiveBulkOperation.type === 'analyze-all' ? t('dashboard.stopAnalyzeAll') : t('dashboard.stopFetchAnalyzeAll')}
                </Button>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('websiteSources.title')}</p>
              <div className="flex gap-2">
                <Button
                  onClick={() => fetchAllWebsites()}
                  disabled={loadingActions.has('fetch-all-ws') || loadingActions.has('analyze-all-ws') || anyWebsiteAnalyzing}
                  size="sm"
                  className="flex-1 h-8"
                >
                  <RefreshCw size={12} className="mr-1" />
                  {t('dashboard.fetchAll')}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => analyzeAllWebsites()}
                  disabled={loadingActions.has('analyze-all-ws') || loadingActions.has('fetch-all-ws') || anyWebsiteAnalyzing}
                  size="sm"
                  className="flex-1 h-8"
                >
                  <Bot size={12} className="mr-1" />
                  {t('dashboard.analyzeAll')}
                </Button>
              </div>
              {anyWebsiteAnalyzing && (
                <Button
                  variant="destructive"
                  onClick={() => stopAllWebsites()}
                  size="sm"
                  className="w-full h-7 text-xs"
                >
                  <Square size={10} className="mr-1" />
                  {t('dashboard.stopAnalyzeAll')}
                </Button>
              )}
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('dashboard.cronJob')}</p>
              <div className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <Timer size={12} className={cronRunning ? 'text-green-500' : 'text-gray-400'} />
                  <span className="text-xs font-medium">{cronRunning ? t('dashboard.running') : t('dashboard.stopped')}</span>
                </div>
                <Button
                  variant={cronRunning ? 'destructive' : 'default'}
                  onClick={() => toggleCron()}
                  size="sm"
                  className="h-7 px-2"
                >
                  {cronRunning ? <Square size={10} /> : <Play size={10} />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('dashboard.realTimeListener')}</p>
              <div className="flex items-center justify-between p-2 rounded-lg bg-muted/50">
                <div className="flex items-center gap-2">
                  <Radio size={12} className={listenerRunning ? 'text-green-500' : 'text-gray-400'} />
                  <span className="text-xs font-medium">{listenerRunning ? t('dashboard.listening') : t('dashboard.stopped')}</span>
                  {listenedChannels.length > 0 && (
                    <span className="text-xs text-muted-foreground">({listenedChannels.length})</span>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    onClick={() => setListenerDialogOpen(true)}
                    size="sm"
                    className="h-7 px-2"
                  >
                    {t('dashboard.manage')}
                  </Button>
                  {listenerRunning && (
                    <Button
                      variant="destructive"
                      onClick={() => stopListener()}
                      size="sm"
                      className="h-7 px-2"
                    >
                      <Square size={10} />
                    </Button>
                  )}
                </div>
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{t('dashboard.other')}</p>
              <Button
                variant="destructive"
                onClick={() => setCleanupDialogOpen(true)}
                disabled={loadingActions.has('cleanup')}
                size="sm"
                className="w-full h-7 text-xs"
              >
                {t('dashboard.cleanupOldMessages')}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Statistics - Glassmorphism */}
        <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
          <CardHeader className="px-4 py-3">
            <CardTitle className="text-sm font-semibold">{t('dashboard.statistics')}</CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {statItems.map(({ icon: Icon, value, label, color }) => (
              <div key={label} className="flex items-center gap-3 p-2 rounded-lg bg-gradient-to-r from-white/50 to-white/30 hover:from-white/70 hover:to-white/50 transition-all">
                <div className={`p-1.5 rounded-md ${color} shrink-0`}>
                  <Icon size={14} />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-base font-bold">{value}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* Main Content - No Scroll */}
      <div className="flex-1 space-y-4">
        {/* Daily Statistics Charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
            <CardHeader className="px-4 py-3">
              <CardTitle className="text-xs font-medium flex items-center gap-2">
                <Briefcase size={14} className="text-blue-500" />
                {t('dashboard.dailyJobPostings')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0">
              <DailyJobsChart days={30} />
            </CardContent>
          </Card>
          <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
            <CardHeader className="px-4 py-3">
              <CardTitle className="text-xs font-medium flex items-center gap-2">
                <Users size={14} className="text-purple-500" />
                {t('dashboard.dailyDevelopersContacted')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0">
              <DailyDevelopersChart days={30} />
            </CardContent>
          </Card>
          <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
            <CardHeader className="px-4 py-3">
              <CardTitle className="text-xs font-medium flex items-center gap-2">
                <CheckCircle2 size={14} className="text-green-500" />
                {t('dashboard.dailyJobsApplied')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0">
              <DailyJobsAppliedChart days={30} />
            </CardContent>
          </Card>
        </div>

        {/* Current Analyzing Message */}
        {Object.keys(currentAnalyzingMessage).length > 0 && (
          <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
            <CardHeader className="px-4 py-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Bot size={14} className="text-blue-500" />
                {t('dashboard.currentlyAnalyzing')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-2">
              {Object.entries(currentAnalyzingMessage).map(([channelUsername, data]) => (
                <div key={channelUsername} className="p-3 rounded-lg bg-gradient-to-r from-blue-50/50 to-purple-50/50 border border-blue-100">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare size={14} className="text-blue-500" />
                    <span className="text-sm font-medium text-blue-700">{channelUsername}</span>
                  </div>
                  {data.message_preview && (
                    <p className="text-sm text-gray-600 line-clamp-3">{data.message_preview}</p>
                  )}
                  {data.message_text && !data.message_preview && (
                    <p className="text-sm text-gray-600 line-clamp-3">{data.message_text.substring(0, 200)}...</p>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* Recent Jobs */}
        <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
          <CardHeader className="px-4 py-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Briefcase size={14} className="text-blue-500" />
              {t('dashboard.recentJobs')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {recentJobs.length === 0 ? (
              <div className="text-center py-6">
                <Briefcase size={32} className="text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">{t('dashboard.noRecentJobs')}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentJobs.map((job) => {
                  const skills = job.skills || [];
                  return (
                    <div key={job.id} className="p-3 rounded-lg bg-gradient-to-r from-white/50 to-white/30 hover:from-white/70 hover:to-white/50 transition-all border border-border">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-medium text-sm truncate flex-1">
                          {job.title || t('jobs.untitledJob')}
                        </span>
                        {job.is_applied && (
                          <Badge variant="default" className="text-xs h-5 px-1.5">{t('jobs.applied')}</Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 truncate">
                        {job.company || t('jobs.unknownCompany')}
                      </p>
                      {job.location && (
                        <p className="text-sm text-gray-500 truncate">
                          <MapPin className="w-3 h-3 inline mr-1" />
                          {job.location}
                        </p>
                      )}
                      {job.role_type && (
                        <div className="flex gap-1 flex-wrap">
                          {job.role_type.split('|').map((role, idx) => (
                            <Badge
                              key={idx}
                              variant="secondary"
                              className="text-xs h-5 px-1.5 bg-blue-50 text-blue-700 border-blue-200"
                            >
                              {role.trim()}
                            </Badge>
                          ))}
                        </div>
                      )}
                      {job.contact && (
                        <p className="text-sm text-gray-500 truncate">
                          <Mail className="w-3 h-3 inline mr-1" />
                          {job.contact}
                        </p>
                      )}
                      {job.summary && (
                        <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                          {job.summary}
                        </p>
                      )}
                      {skills.length > 0 && (
                        <div className="flex gap-1 mt-1.5 flex-wrap">
                          {skills.slice(0, 3).map((skill: string, idx: number) => (
                            <span key={idx} className="text-sm px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded-md">
                              {skill}
                            </span>
                          ))}
                          {skills.length > 3 && (
                            <span className="text-xs text-gray-400">+{skills.length - 3}</span>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                          <MessageSquare className="w-3 h-3" />
                          {job.channel_name || job.channel?.username || t('common.unknown')}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {job.message?.date
                            ? new Date(job.message.date).toLocaleDateString()
                            : t('common.unknown')
                          }
                        </span>
                      </div>
                      <div className="mt-2 pt-2 border-t">
                        <Button
                          size="sm"
                          variant="outline"
                          className="w-full text-xs"
                          onClick={() => navigate(`/jobs?jobId=${job.id}`)}
                        >
                          {t('common.view')}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Developers */}
        <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
          <CardHeader className="px-4 py-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Users size={14} className="text-purple-500" />
              {t('dashboard.recentDevelopers')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {recentDevelopers.length === 0 ? (
              <div className="text-center py-6">
                <Users size={32} className="text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">{t('dashboard.noRecentDevelopers')}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {recentDevelopers.map((dev) => {
                  const skills = dev.skills || [];
                  return (
                    <div key={dev.id} className="p-3 rounded-lg bg-gradient-to-r from-white/50 to-white/30 hover:from-white/70 hover:to-white/50 transition-all border border-border">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-medium text-sm truncate flex-1">
                          {dev.name || t('developers.unnamedDeveloper')}
                        </span>
                        {dev.is_contacted && (
                          <Badge variant="default" className="text-xs h-5 px-1.5">{t('developers.contacted')}</Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 truncate">
                        {dev.looking_for_work ? t('developers.lookingForWork') : t('developers.notLooking')}
                      </p>
                      {dev.experience && (
                        <p className="text-sm text-gray-500 truncate">
                          <Briefcase className="w-3 h-3 inline mr-1" />
                          {dev.experience}
                        </p>
                      )}
                      {dev.contact && (
                        <p className="text-sm text-gray-500 truncate">
                          <Mail className="w-3 h-3 inline mr-1" />
                          {dev.contact}
                        </p>
                      )}
                      {dev.github && (
                        <p className="text-sm text-gray-500 truncate">
                          <ExternalLink className="w-3 h-3 inline mr-1" />
                          GitHub: {dev.github}
                        </p>
                      )}
                      {dev.linkedin && (
                        <p className="text-sm text-gray-500 truncate">
                          <ExternalLink className="w-3 h-3 inline mr-1" />
                          LinkedIn: {dev.linkedin}
                        </p>
                      )}
                      {dev.summary && (
                        <p className="text-sm text-gray-600 mt-2 line-clamp-2">
                          {dev.summary}
                        </p>
                      )}
                      {skills.length > 0 && (
                        <div className="flex gap-1 mt-1.5 flex-wrap">
                          {skills.slice(0, 3).map((skill: string, idx: number) => (
                            <span key={idx} className="text-sm px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded-md">
                              {skill}
                            </span>
                          ))}
                          {skills.length > 3 && (
                            <span className="text-xs text-gray-400">+{skills.length - 3}</span>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-1 mt-1 text-xs text-gray-400">
                        <MessageSquare className="w-3 h-3" />
                        @{dev.channel?.username || t('common.unknown')}
                      </div>
                      <div className="mt-2 pt-2 border-t">
                        <Button
                          size="sm"
                          variant="outline"
                          className="w-full text-xs"
                          onClick={() => navigate(`/developers?developerId=${dev.id}`)}
                        >
                          {t('common.view')}
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Cleanup Confirmation Dialog */}
      <Dialog open={cleanupDialogOpen} onOpenChange={setCleanupDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('dashboard.cleanupOldMessages')}</DialogTitle>
            <DialogDescription>
              {t('dashboard.deleteMessagesOlder', { days: cleanupDays })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t('common.daysToKeep')}</label>
              <input
                type="number"
                min="1"
                value={cleanupDays}
                onChange={(e) => setCleanupDays(parseInt(e.target.value) || 30)}
                className="w-full mt-1 px-3 py-2 border rounded-md"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCleanupDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={cleanupOldMessages} disabled={loadingActions.has('cleanup')}>
              {loadingActions.has('cleanup') ? t('common.cleaning') : t('common.cleanupOldMessages')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unified Manage Listening Dialog */}
      <Dialog
        open={listenerDialogOpen}
        onOpenChange={setListenerDialogOpen}
      >
        <DialogContent className="max-w-lg w-full sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('dashboard.manageListenerChannels')}</DialogTitle>
            <DialogDescription>
              {channels.filter(c => listenedChannels.includes(c.username)).length} of {channels.length} {t('dashboard.channels')} {t('dashboard.listening')}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <div className="space-y-2 max-h-[60vh] sm:max-h-80 overflow-y-auto">
              {channels.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">{t('dashboard.noChannels')}</p>
              ) : (
                channels.map((channel) => {
                  const isListening = listenedChannels.includes(channel.username);
                  const actionKey = `listener-toggle-${channel.id}`;
                  return (
                    <div
                      key={channel.id}
                      className={`flex items-center justify-between p-3 rounded ${
                        channel.is_active ? 'bg-muted' : 'bg-gray-100 opacity-60'
                      }`}
                    >
                      <div className="flex-1 min-w-0 mr-3">
                        <div className="font-medium text-sm">{channel.username}</div>
                        {channel.name && (
                          <div className="text-xs text-muted-foreground truncate">{channel.name}</div>
                        )}
                        <div className="flex items-center gap-2 mt-0.5">
                          {!channel.is_active && (
                            <span className="text-xs text-gray-400">{t('channels.inactive')}</span>
                          )}
                          {isListening && (
                            <span className="text-xs text-green-600 font-medium">{t('dashboard.listening')}</span>
                          )}
                        </div>
                      </div>
                      <Button
                        variant={isListening ? 'destructive' : 'default'}
                        size="sm"
                        onClick={() => toggleChannelListener(channel)}
                        disabled={loadingActions.has(actionKey)}
                        className="h-8 sm:h-7 px-3 sm:px-3 text-xs shrink-0"
                      >
                        {loadingActions.has(actionKey)
                          ? '...'
                          : isListening
                            ? t('common.stop')
                            : t('common.listen')}
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setListenerDialogOpen(false)} className="w-full sm:w-auto">
              {t('common.close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Dashboard;
