import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  ChevronRight,
  Loader2,
  Zap,
} from 'lucide-react';
import api from '@/services/api';
import type { Channel, Stats, WebsiteSource } from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

const Dashboard = () => {
  const { t } = useTranslation();
  const [stats, setStats] = useState<Stats | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [websiteSources, setWebsiteSources] = useState<WebsiteSource[]>([]);
  const [activeTab, setActiveTab] = useState('channels');
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const [cronRunning, setCronRunning] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const [cleanupDialogOpen, setCleanupDialogOpen] = useState(false);
  const [cleanupDays, setCleanupDays] = useState(30);
  const [bulkOperation, setBulkOperation] = useState<{ id: string; type: 'analyze-all' | 'fetch-analyze-all' } | null>(null);
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');

  const { progress: wsProgress, channelProgress, operations, bulkOperations, stoppingChannels, tokenUsage, messageResults, currentAnalyzingMessage, requestStop } = useWebSocketProgress();

  useEffect(() => {
    if (wsProgress && (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error' || wsProgress.type === 'fetch_complete')) {
      loadData();
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
    const interval = setInterval(() => {
      loadData();
      checkCronStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, [offset]);

  const loadData = async () => {
    try {
      const [statsData, channelsData, sourcesData] = await Promise.all([
        api.getStats(),
        api.getChannels({ limit, offset }),
        api.getWebsiteSources(),
      ]);
      setStats(statsData);
      setChannels(channelsData.channels);
      setTotal(channelsData.total || 0);
      setWebsiteSources(sourcesData.sources || []);
      setInitialLoading(false);
    } catch (error) {
      setInitialLoading(false);
    }
  };

  const handleNext = () => {
    const newOffset = offset + limit;
    setSearchParams({ offset: newOffset.toString() });
  };

  const handlePrevious = () => {
    const newOffset = Math.max(0, offset - limit);
    setSearchParams({ offset: newOffset.toString() });
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

  const fetchChannel = async (channelId: number) => {
    try {
      const data = await withLoading(`fetch-${channelId}`, () => api.fetchChannel(channelId));
      if (data.success) {
        showToast('success', t('dashboard.fetchedMessages', { count: data.new_messages, days: data.days_back_used }));
        loadData();
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const analyzeChannel = async (channelId: number) => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }

      const data = await withLoading(`analyze-${channelId}`, () => api.analyzeChannel(channelId));
      if (data.success) {
        if (data.message) {
          // Background task started
          showToast('success', data.message);
        } else if (data.stopped) {
          showToast('info', t('dashboard.analyzeStopped', { analyzed: data.analyzed, jobs: data.jobs_found, remaining: data.remaining }));
        } else {
          showToast('success', t('dashboard.analyzeComplete', { analyzed: data.analyzed, jobs: data.jobs_found, devs: data.developers_found }));
        }
        // Reload data after a delay to see results
        setTimeout(() => loadData(), 3000);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || data.message || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const stopAnalyzeChannel = async (channelId: number, channelUsername: string) => {
    try {
      // Mark channel as stopping immediately for UI feedback
      requestStop(channelId, channelUsername);
      const data = await api.stopAnalyze(channelId);
      if (data.success) {
        showToast('success', t('dashboard.stopSignalSent'));
      } else {
        showToast('warning', data.message || t('dashboard.noActiveAnalysis'));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
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

  const fetchWebsiteSource = async (sourceId: number) => {
    try {
      const data = await withLoading(`fetch-ws-${sourceId}`, () => api.fetchWebsiteSource(sourceId));
      if (data.success) {
        showToast('success', t('dashboard.fetchedMessages', { count: data.new_messages ?? data.fetched ?? 0, days: data.days_back_used ?? 0 }));
        loadData();
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || data.detail || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const analyzeWebsiteSource = async (sourceId: number) => {
    try {
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }
      const data = await withLoading(`analyze-ws-${sourceId}`, () => api.analyzeWebsiteSource(sourceId));
      if (data.success) {
        showToast('success', data.message || t('dashboard.analyzeComplete', { analyzed: data.analyzed ?? 0, jobs: data.jobs_found ?? 0, devs: 0 }));
        setTimeout(() => loadData(), 2000);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || data.detail || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const stopWebsiteSource = async (sourceId: number, sourceName: string) => {
    try {
      requestStop(sourceId, sourceName);
      const data = await api.stopWebsiteSource(sourceId);
      if (data.success) {
        showToast('success', t('dashboard.stopSignalSent'));
      } else {
        showToast('warning', data.message || t('dashboard.noActiveAnalysis'));
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
    <div className="flex gap-6">
      {/* Sidebar Navigation */}
      <div className="w-72 shrink-0 space-y-4">
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

        {/* Live Analysis */}
        <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
          <CardHeader className="px-4 py-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Bot size={16} className="text-blue-500" />
              {t('dashboard.liveAnalysis')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            {Object.keys(currentAnalyzingMessage).length === 0 && Object.keys(messageResults).length === 0 ? (
              <div className="text-center py-8">
                <Bot size={32} className="text-muted-foreground/30 mx-auto mb-2" />
                <p className="text-xs text-muted-foreground">{t('dashboard.noActiveAnalysis')}</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-64 overflow-y-auto">
                {Object.entries(currentAnalyzingMessage).map(([channel, msg]) => (
                  <div key={channel} className="border border-blue-200 rounded-lg p-3 bg-gradient-to-br from-blue-50 to-blue-100/50">
                    <div className="flex items-center gap-2 mb-2">
                      <Loader2 size={14} className="text-blue-600 animate-spin" />
                      <span className="text-xs font-semibold text-blue-900">{channel}</span>
                    </div>
                    <p className="text-xs text-gray-700 line-clamp-2">{msg.message_text || msg.message_preview}</p>
                  </div>
                ))}
                {Object.entries(messageResults).map(([channel, results]) => (
                  <div key={channel} className="border border-border rounded-lg p-3 bg-gradient-to-br from-muted to-muted/50">
                    <div className="flex items-center gap-2 mb-2">
                      <Radio size={14} className="text-blue-500" />
                      <span className="text-xs font-semibold">{channel}</span>
                      <Badge variant="secondary" className="text-xs">{results.length}</Badge>
                    </div>
                    <div className="space-y-1">
                      {results.slice(-2).map((result: any, idx: number) => (
                        <div key={idx} className="bg-white p-2 rounded border text-xs">
                          <Badge variant={result.status === 'success' ? 'default' : result.status === 'failed' ? 'destructive' : 'secondary'} className="text-[10px]">
                            {result.status}
                          </Badge>
                          <span className="ml-1 font-medium">{result.category}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Channels / Website Sources */}
        <Card className="backdrop-blur-xl bg-white/70 border border-white/20 shadow-lg">
          <CardHeader className="px-4 py-3">
            <div className="flex justify-between items-center">
              <div className="flex gap-1 bg-muted p-1 rounded-lg">
                <button
                  onClick={() => setActiveTab('channels')}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${activeTab === 'channels' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  <Radio size={12} />
                  {t('dashboard.channels')} ({total})
                </button>
                <button
                  onClick={() => setActiveTab('websites')}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${activeTab === 'websites' ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'}`}
                >
                  <RefreshCw size={12} />
                  {t('websiteSources.title')} ({websiteSources.length})
                </button>
              </div>
              <Button asChild variant="ghost" size="sm" className="h-8">
                <Link to={activeTab === 'channels' ? '/channels' : '/websites'} className="text-xs">
                  {t('dashboard.manage')} <ChevronRight size={12} className="inline ml-1" />
                </Link>
              </Button>
            </div>
          </CardHeader>

            <CardContent className="p-0">
              {activeTab === 'channels' ? (
                <>
                  {initialLoading ? (
                    <div className="px-6 py-12 text-center">
                      <Loader2 className="w-6 h-6 text-muted-foreground/50 animate-spin mx-auto mb-3" />
                      <p className="text-sm text-muted-foreground">{t('dashboard.loadingChannels')}</p>
                    </div>
                  ) : channels.length > 0 ? (
                    <>
                      {channels.map((channel) => (
                        <div key={channel.id} className="px-6 py-4 border-b border-border last:border-b-0 hover:bg-muted/50 transition-colors">
                          <div className="flex justify-between items-center gap-4">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <p className="font-semibold text-foreground truncate">{channel.username}</p>
                                <Badge variant={channel.is_active ? 'default' : 'secondary'} className="text-xs">
                                  {channel.is_active ? t('channels.active') : t('channels.inactive')}
                                </Badge>
                              </div>
                              {channel.name && <p className="text-sm text-muted-foreground truncate">{channel.name}</p>}
                              <p className="text-xs text-muted-foreground mt-1.5">
                                {(channel.message_count || 0).toLocaleString()} msgs &bull; {(channel.job_count || 0).toLocaleString()} jobs
                                {(channel.last_fetch_new_count || 0) > 0 && (
                                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    +{channel.last_fetch_new_count} {t('websites.fetched')}
                                  </span>
                                )}
                                {(channel.pending_count || 0) > 0 && (
                                  <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                                    {channel.pending_count} {t('dashboard.pendingAnalysis')}
                                  </span>
                                )}
                              </p>
                              {channelProgress[channel.username] && (
                                <div className="mt-3">
                                  <div className="flex justify-between text-xs mb-1.5">
                                    <span className={stoppingChannels[channel.username] ? 'text-orange-600 font-medium' : 'text-blue-600 font-medium'}>
                                      {stoppingChannels[channel.username] ? t('dashboard.stoppingProgress') : t('dashboard.analyzingProgress')}
                                    </span>
                                    <span className="text-muted-foreground">{channelProgress[channel.username].analyzed}/{channelProgress[channel.username].total}</span>
                                  </div>
                                  <div className="w-full bg-muted rounded-full h-2.5">
                                    <div
                                      className={`h-2.5 rounded-full transition-all ${stoppingChannels[channel.username] ? 'bg-orange-500' : 'bg-blue-600'}`}
                                      style={{ width: `${(channelProgress[channel.username].total > 0 ? (channelProgress[channel.username].analyzed / channelProgress[channel.username].total) * 100 : 0)}%` }}
                                    />
                                  </div>
                                  {tokenUsage[channel.username] && (
                                    <div className="flex justify-between text-xs mt-1.5 text-muted-foreground">
                                      <span>🤖 {(tokenUsage[channel.username].total / 1000).toFixed(1)}k tokens</span>
                                      <span>⬆{(tokenUsage[channel.username].input / 1000).toFixed(1)}k ⬇{(tokenUsage[channel.username].output / 1000).toFixed(1)}k</span>
                                    </div>
                                  )}
                                  {messageResults[channel.username] && messageResults[channel.username].length > 0 && (
                                    <div className="mt-2 text-xs">
                                      <div className="flex gap-2 text-muted-foreground">
                                        <span>✓ {messageResults[channel.username].filter((r: any) => r.status === 'success').length}</span>
                                        <span className="text-orange-500">⚠ {messageResults[channel.username].filter((r: any) => r.status === 'json_cutoff').length}</span>
                                        <span className="text-red-500">✗ {messageResults[channel.username].filter((r: any) => r.status === 'failed').length}</span>
                                        <span className="text-muted-foreground/50">○ {messageResults[channel.username].filter((r: any) => r.status === 'other').length}</span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            <div className="flex gap-2 flex-shrink-0">
                              {!(loadingActions.has(`fetch-${channel.id}`) || loadingActions.has(`analyze-${channel.id}`) || !!operations[channel.username]) && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => fetchChannel(channel.id)}
                                    disabled={loadingActions.has(`fetch-${channel.id}`)}
                                    className="h-9"
                                  >
                                    <RefreshCw size={14} className="mr-2" />
                                    {loadingActions.has(`fetch-${channel.id}`) ? t('dashboard.fetching') : t('channels.fetch')}
                                  </Button>
                                  <Button
                                    size="sm"
                                    onClick={() => analyzeChannel(channel.id)}
                                    disabled={loadingActions.has(`analyze-${channel.id}`)}
                                    className="h-9"
                                  >
                                    <Bot size={14} className="mr-2" />
                                    {loadingActions.has(`analyze-${channel.id}`) ? t('dashboard.analyzing') : t('channels.analyze')}
                                  </Button>
                                </>
                              )}
                              {(loadingActions.has(`fetch-${channel.id}`) || loadingActions.has(`analyze-${channel.id}`) || !!operations[channel.username]) && (
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => stopAnalyzeChannel(channel.id, channel.username)}
                                  title={t('common.stop')}
                                  disabled={stoppingChannels[channel.id] || stoppingChannels[channel.username]}
                                  className="h-9"
                                >
                                  <Square size={14} className="mr-2" />
                                  {stoppingChannels[channel.id] || stoppingChannels[channel.username] ? t('channels.stopping') : t('common.stop')}
                                </Button>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                      {/* Pagination */}
                      <div className="px-6 py-4 border-t border-border flex items-center justify-between bg-muted/30">
                        <Button variant="outline" size="sm" onClick={handlePrevious} disabled={offset === 0} className="h-9">
                          {t('common.previous')}
                        </Button>
                        <span className="text-sm text-muted-foreground">
                          Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)} ({offset + 1}-{Math.min(offset + limit, total)} of {total})
                        </span>
                        <Button variant="outline" size="sm" onClick={handleNext} disabled={offset + limit >= total} className="h-9">
                          {t('common.next')}
                        </Button>
                      </div>
                    </>
                  ) : (
                    <div className="px-6 py-12 text-center">
                      <Radio size={48} className="text-muted-foreground/20 mx-auto mb-4" />
                      <p className="text-sm text-muted-foreground">{t('dashboard.noChannelsConfigured')}</p>
                      <Button asChild variant="outline" size="sm" className="mt-4 h-9">
                        <Link to="/channels">{t('dashboard.addFirstChannel')}</Link>
                      </Button>
                    </div>
                  )}
                </>
              ) : (
                <>
                  {websiteSources.length > 0 ? (
                    websiteSources.map((source) => (
                      <div key={source.id} className="px-6 py-4 border-b border-border last:border-b-0 hover:bg-muted/50 transition-colors">
                        <div className="flex justify-between items-center gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="font-semibold text-foreground truncate">{source.name}</p>
                              <Badge variant={source.is_active ? 'default' : 'secondary'} className="text-xs">
                                {source.is_active ? t('channels.active') : t('channels.inactive')}
                              </Badge>
                              <Badge variant="outline" className="text-xs">{source.site_type}</Badge>
                            </div>
                            <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-500 hover:underline truncate block">
                              {source.url}
                            </a>
                            <p className="text-xs text-muted-foreground mt-1.5">
                              {(source.message_count || 0).toLocaleString()} posts &bull; {(source.job_count || 0).toLocaleString()} jobs
                              {(source.last_fetch_new_count || 0) > 0 && (
                                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                  +{source.last_fetch_new_count} {t('websites.fetched')}
                                </span>
                              )}
                              {(source.pending_count || 0) > 0 && (
                                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                                  {source.pending_count} {t('dashboard.pendingAnalysis')}
                                </span>
                              )}
                            </p>
                            {source.last_fetch_at && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {t('websiteSources.lastFetch')}: {new Date(source.last_fetch_at).toLocaleString()}
                              </p>
                            )}
                            {channelProgress[source.name] && (
                              <div className="mt-3">
                                <div className="flex justify-between text-xs mb-1.5">
                                  <span className={stoppingChannels[source.name] ? 'text-orange-600 font-medium' : 'text-blue-600 font-medium'}>
                                    {stoppingChannels[source.name] ? t('dashboard.stoppingProgress') : t('dashboard.analyzingProgress')}
                                  </span>
                                  <span className="text-muted-foreground">{channelProgress[source.name].analyzed}/{channelProgress[source.name].total}</span>
                                </div>
                                <div className="w-full bg-muted rounded-full h-2.5">
                                  <div
                                    className={`h-2.5 rounded-full transition-all ${stoppingChannels[source.name] ? 'bg-orange-500' : 'bg-blue-600'}`}
                                    style={{ width: `${channelProgress[source.name].total > 0 ? (channelProgress[source.name].analyzed / channelProgress[source.name].total) * 100 : 0}%` }}
                                  />
                                </div>
                                {tokenUsage[source.name] && (
                                  <div className="flex justify-between text-xs mt-1.5 text-muted-foreground">
                                    <span>🤖 {(tokenUsage[source.name].total / 1000).toFixed(1)}k tokens</span>
                                    <span>⬆{(tokenUsage[source.name].input / 1000).toFixed(1)}k ⬇{(tokenUsage[source.name].output / 1000).toFixed(1)}k</span>
                                  </div>
                                )}
                                {messageResults[source.name] && messageResults[source.name].length > 0 && (
                                  <div className="mt-2 text-xs">
                                    <div className="flex gap-2 text-muted-foreground">
                                      <span>✓ {messageResults[source.name].filter((r: any) => r.status === 'success').length}</span>
                                      <span className="text-orange-500">⚠ {messageResults[source.name].filter((r: any) => r.status === 'json_cutoff').length}</span>
                                      <span className="text-red-500">✗ {messageResults[source.name].filter((r: any) => r.status === 'failed').length}</span>
                                      <span className="text-muted-foreground/50">○ {messageResults[source.name].filter((r: any) => r.status === 'other').length}</span>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          <div className="flex gap-2 flex-shrink-0">
                            {!(loadingActions.has(`fetch-ws-${source.id}`) || loadingActions.has(`analyze-ws-${source.id}`) || !!wsSourceAnalyzing[source.name]) && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => fetchWebsiteSource(source.id)}
                                  className="h-9"
                                >
                                  <RefreshCw size={14} className="mr-2" />
                                  {t('channels.fetch')}
                                </Button>
                                <Button
                                  size="sm"
                                  onClick={() => analyzeWebsiteSource(source.id)}
                                  className="h-9"
                                >
                                  <Bot size={14} className="mr-2" />
                                  {t('channels.analyze')}
                                </Button>
                              </>
                            )}
                            {(loadingActions.has(`fetch-ws-${source.id}`) || loadingActions.has(`analyze-ws-${source.id}`) || !!wsSourceAnalyzing[source.name]) && (
                              <Button
                                size="sm"
                                variant="destructive"
                                onClick={() => stopWebsiteSource(source.id, source.name)}
                                disabled={stoppingChannels[source.id] || stoppingChannels[source.name]}
                                className="h-9"
                              >
                                <Square size={14} className="mr-2" />
                                {stoppingChannels[source.id] || stoppingChannels[source.name] ? t('channels.stopping') : t('common.stop')}
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="px-6 py-12 text-center">
                      <RefreshCw size={48} className="text-muted-foreground/20 mx-auto mb-4" />
                      <p className="text-sm text-muted-foreground">{t('websiteSources.noSources')}</p>
                      <Button asChild variant="outline" size="sm" className="mt-4 h-9">
                        <Link to="/websites">{t('dashboard.manage')}</Link>
                      </Button>
                    </div>
                  )}
                </>
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
    </div>
  );
};

export default Dashboard;
