import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
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
  Trash2,
  RotateCcw,
  ChevronRight,
  Loader2,
  Zap,
} from 'lucide-react';
import api from '@/services/api';
import type { Channel, Stats } from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

const Dashboard = () => {
  const { t } = useTranslation();
  const [stats, setStats] = useState<Stats | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
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

  const { progress: wsProgress, channelProgress, operations, bulkOperations, stoppingChannels, tokenUsage, messageResults, requestStop } = useWebSocketProgress();

  useEffect(() => {
    if (wsProgress && (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error' || wsProgress.type === 'fetch_complete')) {
      loadData();
    }
  }, [wsProgress]);

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
      const [statsData, channelsData] = await Promise.all([
        api.getStats(),
        api.getChannels({ limit, offset }),
      ]);
      setStats(statsData);
      setChannels(channelsData.channels);
      setTotal(channelsData.total || 0);
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

  const fetchAnalyzeAll = async () => {
    try {
      // Check if Ollama is available before attempting analysis (fetch-analyze includes analysis)
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }

      const data = await withLoading('fetch-analyze-all', () => api.fetchAnalyzeAll());
      if (data.success) {
        if (data.operation_id) {
          setBulkOperation({ id: data.operation_id, type: 'fetch-analyze-all' });
        }
        showToast('success', t('dashboard.fetchAnalyzeStarted', { count: data.channels }));
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const reanalyzeSkipped = async () => {
    try {
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }

      const data = await withLoading('reanalyze-skipped', () => api.reanalyzeSkipped());
      if (data.success) {
        showToast('success', t('dashboard.reanalysisStartedSkipped'));
        setTimeout(() => loadData(), 2000);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const reanalyzeMessages = async () => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showToast('error', t('dashboard.ollamaUnavailable'));
        return;
      }

      const data = await withLoading('reanalyze', () => api.reanalyzeMessages());
      if (data.success) {
        showToast('success', t('dashboard.reanalysisComplete', { count: data.reanalyzed }));
        setTimeout(() => loadData(), 1500);
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
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
    <div className="space-y-6">
      {/* Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader className="px-4 py-3 pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Briefcase size={14} className="text-blue-500" />
              {t('dashboard.dailyJobPostings')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <DailyJobsChart days={30} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="px-4 py-3 pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Users size={14} className="text-purple-500" />
              {t('dashboard.dailyDevelopersContacted')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <DailyDevelopersChart days={30} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="px-4 py-3 pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <CheckCircle2 size={14} className="text-green-500" />
              {t('dashboard.dailyJobsApplied')}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 pt-0">
            <DailyJobsAppliedChart days={30} />
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          {/* Stats */}
          <Card>
            <CardHeader className="px-4 py-3 pb-2">
              <CardTitle className="text-sm">{t('dashboard.statistics')}</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0">
              <div className="grid grid-cols-2 gap-2">
                {statItems.map(({ icon: Icon, value, label, color }) => (
                  <div key={label} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50">
                    <div className={`p-1.5 rounded-md ${color} shrink-0`}>
                      <Icon size={14} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-muted-foreground">{label}</p>
                      <p className="text-base font-bold truncate">{value}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader className="px-4 py-3 pb-2">
              <CardTitle className="flex items-center gap-1.5 text-sm">
                <Zap size={14} className="text-yellow-500" />
                {t('dashboard.quickActions')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0 space-y-3">
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{t('dashboard.allChannels')}</p>
                <div className="flex flex-col gap-2">
                  <Button
                    className="w-full justify-start"
                    onClick={() => fetchAll()}
                    disabled={loadingActions.has('fetch-all') || Object.keys(operations).length > 0 || effectiveBulkOperation !== null}
                  >
                    <RefreshCw size={14} className="mr-2" />
                    {loadingActions.has('fetch-all') ? t('dashboard.fetching') : (Object.keys(operations).length > 0 || effectiveBulkOperation) ? t('dashboard.operationInProgress') : t('dashboard.fetchAll')}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => analyzeAll()}
                    disabled={loadingActions.has('analyze-all') || Object.keys(operations).length > 0 || effectiveBulkOperation !== null}
                  >
                    <Bot size={14} className="mr-2" />
                    {loadingActions.has('analyze-all') ? t('dashboard.analyzing') : (Object.keys(operations).length > 0 || effectiveBulkOperation) ? t('dashboard.operationInProgress') : t('dashboard.analyzeAll')}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => fetchAnalyzeAll()}
                    disabled={loadingActions.has('fetch-analyze-all') || Object.keys(operations).length > 0 || effectiveBulkOperation !== null}
                  >
                    <Zap size={14} className="mr-2" />
                    {loadingActions.has('fetch-analyze-all') ? t('dashboard.processing') : (Object.keys(operations).length > 0 || effectiveBulkOperation) ? t('dashboard.operationInProgress') : t('dashboard.fetchAnalyzeAll')}
                  </Button>
                  {effectiveBulkOperation && (
                    <Button
                      className="w-full justify-start"
                      variant="destructive"
                      onClick={() => stopBulkOperation()}
                    >
                      <Square size={14} className="mr-2" />
                      {effectiveBulkOperation.type === 'analyze-all' ? t('dashboard.stopAnalyzeAll') : t('dashboard.stopFetchAnalyzeAll')}
                    </Button>
                  )}
                </div>
              </div>

              <Separator />

              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{t('dashboard.cronJob')}</p>
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border mb-2">
                  <div className="flex items-center gap-2">
                    <Timer size={14} className={cronRunning ? 'text-green-500' : 'text-gray-400'} />
                    <span className="text-sm font-medium">{cronRunning ? t('dashboard.running') : t('dashboard.stopped')}</span>
                    {cronRunning && (
                      <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                    )}
                  </div>
                  <Badge variant={cronRunning ? 'default' : 'secondary'}>
                    {cronRunning ? 'Active' : 'Idle'}
                  </Badge>
                </div>
                <Button
                  className="w-full justify-start"
                  variant={cronRunning ? 'destructive' : 'default'}
                  onClick={() => toggleCron()}
                >
                  {cronRunning ? <Square size={14} className="mr-2" /> : <Play size={14} className="mr-2" />}
                  {cronRunning ? t('dashboard.stopCronJob') : t('dashboard.startCronJob')}
                </Button>
              </div>

              <Separator />

              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">{t('dashboard.other')}</p>
                <div className="flex flex-col gap-2">
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => reanalyzeSkipped()}
                    disabled={loadingActions.has('reanalyze-skipped')}
                  >
                    <RotateCcw size={14} className="mr-2" />
                    {loadingActions.has('reanalyze-skipped') ? t('dashboard.reanalyzing') : t('dashboard.reanalyzeSkipped')}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => reanalyzeMessages()}
                    disabled={loadingActions.has('reanalyze')}
                  >
                    <RefreshCw size={14} className="mr-2" />
                    {loadingActions.has('reanalyze') ? t('dashboard.reanalyzing') : t('dashboard.reanalyzeAll')}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="destructive"
                    onClick={() => setCleanupDialogOpen(true)}
                    disabled={loadingActions.has('cleanup')}
                  >
                    <Trash2 size={14} className="mr-2" />
                    {loadingActions.has('cleanup') ? t('common.cleaning') : t('dashboard.cleanupOldMessages')}
                  </Button>
                </div>
              </div>

            </CardContent>
          </Card>
        </div>

        {/* Channels List */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="px-4 py-3 pb-2">
              <div className="flex justify-between items-center">
                <CardTitle className="flex items-center gap-1.5 text-sm">
                  <Radio size={14} className="text-blue-500" />
                  {t('dashboard.channels')} ({total})
                </CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/channels" className="text-xs">{t('dashboard.manage')} <ChevronRight size={12} className="inline" /></Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {initialLoading ? (
                <div className="px-4 py-8 text-center">
                  <Loader2 className="w-5 h-5 text-gray-400 animate-spin mx-auto mb-2" />
                  <p className="text-sm text-gray-500">{t('dashboard.loadingChannels')}</p>
                </div>
              ) : channels.length > 0 ? (
                <>
                  {channels.map((channel) => (
                    <div key={channel.id} className="px-4 py-3 border-b last:border-b-0 hover:bg-gray-50 transition-colors">
                      <div className="flex justify-between items-center gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <p className="font-semibold text-gray-900 truncate">{channel.username}</p>
                            <Badge variant={channel.is_active ? 'default' : 'secondary'} className="text-xs">
                              {channel.is_active ? t('channels.active') : t('channels.inactive')}
                            </Badge>
                          </div>
                          {channel.name && <p className="text-xs text-gray-500 truncate">{channel.name}</p>}
                          <p className="text-xs text-gray-400 mt-0.5">
                            {(channel.message_count || 0).toLocaleString()} msgs &bull; {(channel.job_count || 0).toLocaleString()} jobs
                            {(channel.last_fetch_new_count || 0) > 0 && (
                              <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                +{channel.last_fetch_new_count} {t('websites.fetched')}
                              </span>
                            )}
                            {(channel.pending_count || 0) > 0 && (
                              <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                                {channel.pending_count} {t('dashboard.pendingAnalysis')}
                              </span>
                            )}
                          </p>
                          {channelProgress[channel.username] && (
                            <div className="mt-2">
                              <div className="flex justify-between text-xs mb-1">
                                <span className={stoppingChannels[channel.username] ? 'text-orange-600 font-medium' : ''}>
                                  {stoppingChannels[channel.username] ? t('dashboard.stoppingProgress') : t('dashboard.analyzingProgress')}
                                </span>
                                <span>{channelProgress[channel.username].analyzed}/{channelProgress[channel.username].total}</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full transition-all ${stoppingChannels[channel.username] ? 'bg-orange-500' : 'bg-blue-600'}`}
                                  style={{ width: `${(channelProgress[channel.username].total > 0 ? (channelProgress[channel.username].analyzed / channelProgress[channel.username].total) * 100 : 0)}%` }}
                                />
                              </div>
                              {tokenUsage[channel.username] && (
                                <div className="flex justify-between text-xs mt-1 text-gray-500">
                                  <span>🤖 {(tokenUsage[channel.username].total / 1000).toFixed(1)}k tokens</span>
                                  <span>⬆{(tokenUsage[channel.username].input / 1000).toFixed(1)}k ⬇{(tokenUsage[channel.username].output / 1000).toFixed(1)}k</span>
                                </div>
                              )}
                              {messageResults[channel.username] && messageResults[channel.username].length > 0 && (
                                <div className="mt-2 text-xs">
                                  <div className="flex gap-2 text-gray-500">
                                    <span>✓ {messageResults[channel.username].filter((r: any) => r.status === 'success').length}</span>
                                    <span className="text-orange-500">⚠ {messageResults[channel.username].filter((r: any) => r.status === 'json_cutoff').length}</span>
                                    <span className="text-red-500">✗ {messageResults[channel.username].filter((r: any) => r.status === 'failed').length}</span>
                                    <span className="text-gray-400">○ {messageResults[channel.username].filter((r: any) => r.status === 'other').length}</span>
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
                              >
                                <RefreshCw size={12} className="mr-1" />
                                {loadingActions.has(`fetch-${channel.id}`) ? t('dashboard.fetching') : t('channels.fetch')}
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => analyzeChannel(channel.id)}
                                disabled={loadingActions.has(`analyze-${channel.id}`)}
                              >
                                <Bot size={12} className="mr-1" />
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
                            >
                              <Square size={12} className="mr-1" />
                              {stoppingChannels[channel.id] || stoppingChannels[channel.username] ? t('channels.stopping') : t('common.stop')}
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  {/* Pagination */}
                  <div className="px-4 py-3 border-t flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handlePrevious}
                      disabled={offset === 0}
                    >
                      {t('common.previous')}
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {Math.floor(offset / limit) + 1} of {Math.ceil(total / limit)} ({offset + 1}-{Math.min(offset + limit, total)} of {total})
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleNext}
                      disabled={offset + limit >= total}
                    >
                      {t('common.next')}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="px-4 py-8 text-center">
                  <Radio size={32} className="text-gray-200 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">{t('dashboard.noChannelsConfigured')}</p>
                  <Button asChild variant="outline" size="sm" className="mt-3">
                    <Link to="/channels">{t('dashboard.addFirstChannel')}</Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
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
