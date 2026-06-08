import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
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
  RotateCcw,
  ChevronRight,
  Loader2,
  Zap,
} from 'lucide-react';
import api from '@/services/api';
import type { Channel, Stats } from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

const Dashboard = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const [cronRunning, setCronRunning] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');

  const { progress: wsProgress, channelProgress, operations, stoppingChannels, tokenUsage, requestStop } = useWebSocketProgress();

  useEffect(() => {
    if (wsProgress && (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error' || wsProgress.type === 'fetch_complete')) {
      loadData();
    }
  }, [wsProgress]);

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
        showToast('success', `Fetched ${data.new_messages} new messages from channel (${data.days_back_used}d window)`);
        loadData();
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const analyzeChannel = async (channelId: number) => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showToast('error', 'Ollama is not available. Please check if Ollama is running.');
        return;
      }

      const data = await withLoading(`analyze-${channelId}`, () => api.analyzeChannel(channelId));
      if (data.success) {
        if (data.stopped) {
          showToast('info', `Stopped! Analyzed ${data.analyzed} msgs, ${data.jobs_found} jobs (${data.remaining} remaining)`);
        } else {
          showToast('success', `Analyzed: ${data.analyzed} msgs, ${data.jobs_found} jobs, ${data.developers_found} devs`);
        }
        setTimeout(() => loadData(), 1500);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const stopAnalyzeChannel = async (channelId: number, channelUsername: string) => {
    try {
      // Mark channel as stopping immediately for UI feedback
      requestStop(channelId, channelUsername);
      const data = await api.stopAnalyze(channelId);
      if (data.success) {
        showToast('success', 'Stop signal sent - finishing current message...');
      } else {
        showToast('warning', data.message || 'No active analysis to stop');
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
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
          showToast('success', 'Cron job stopped');
        } else {
          showToast('error', 'Error: ' + (data.message || 'Unknown'));
        }
      } else {
        const data = await api.startCron();
        if (data.success) {
          setCronRunning(true);
          showToast('success', 'Cron job started - fetching messages every 30 minutes');
        } else {
          showToast('error', 'Error: ' + (data.message || 'Unknown'));
        }
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const fetchAll = async () => {
    try {
      const data = await withLoading('fetch-all', () => api.fetchAll());
      if (data.success) {
        const total = data.results.reduce((s: number, r: any) => s + (r.new_messages || 0), 0);
        showToast('success', `Fetched ${total} new messages across all channels`);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const analyzeAll = async () => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showToast('error', 'Ollama is not available. Please check if Ollama is running.');
        return;
      }

      const data = await withLoading('analyze-all', () => api.analyzeAll());
      if (data.success) {
        const totalJobs = data.results.reduce((s: number, r: any) => s + (r.jobs_found || 0), 0);
        const wasStopped = data.results.some((r: any) => r.stopped);
        if (wasStopped) {
          showToast('info', `Stopped! Found ${totalJobs} jobs across channels (some remaining)`);
        } else {
          showToast('success', `Analysis complete! Found ${totalJobs} jobs across all channels`);
        }
        setTimeout(() => loadData(), 1500);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const fetchAnalyzeAll = async () => {
    try {
      // Check if Ollama is available before attempting analysis (fetch-analyze includes analysis)
      if (!stats?.ollama_available) {
        showToast('error', 'Ollama is not available. Please check if Ollama is running.');
        return;
      }

      const data = await withLoading('fetch-analyze-all', () => api.fetchAnalyzeAll());
      if (data.success) {
        const totalJobs = data.results.reduce((s: number, r: any) => s + (r.total_jobs || 0), 0);
        showToast('success', `Complete! Found ${totalJobs} jobs across all channels`);
        setTimeout(() => loadData(), 2000);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const reanalyzeSkipped = async () => {
    try {
      if (!stats?.ollama_available) {
        showToast('error', 'Ollama is not available. Please check if Ollama is running.');
        return;
      }

      const data = await withLoading('reanalyze-skipped', () => api.reanalyzeSkipped());
      if (data.success) {
        showToast('success', 'Re-analysis started for skipped messages');
        setTimeout(() => loadData(), 2000);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const reanalyzeMessages = async () => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showToast('error', 'Ollama is not available. Please check if Ollama is running.');
        return;
      }

      const data = await withLoading('reanalyze', () => api.reanalyzeMessages());
      if (data.success) {
        showToast('success', `Re-analysis complete! Processed ${data.reanalyzed} messages`);
        setTimeout(() => loadData(), 1500);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const statItems = [
    { icon: MessageSquare, value: stats?.total_messages ?? '-', label: 'Total Messages', color: 'text-cyan-600 bg-cyan-100' },
    { icon: Clock, value: stats?.pending_messages ?? '-', label: 'Pending Analysis', color: 'text-yellow-600 bg-yellow-100' },
    { icon: SkipForward, value: stats?.skipped_messages ?? '-', label: 'Skipped', color: 'text-gray-600 bg-gray-100' },
    { icon: Radio, value: stats?.total_channels ?? '-', label: 'Channels', color: 'text-blue-600 bg-blue-100' },
    { icon: Briefcase, value: stats?.job_postings ?? '-', label: 'Job Postings', color: 'text-green-600 bg-green-100' },
    { icon: Users, value: stats?.developers ?? '-', label: 'Developers', color: 'text-purple-600 bg-purple-100' },
    { icon: CheckCircle2, value: stats?.applications?.jobs?.total ?? '-', label: 'Jobs Applied', color: 'text-orange-600 bg-orange-100' },
    { icon: Bot, value: stats?.ollama_available ? 'Online' : 'Offline', label: 'Ollama', color: stats?.ollama_available ? 'text-green-600 bg-green-100' : 'text-red-600 bg-red-100' },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Sidebar */}
        <div className="lg:col-span-1 space-y-4">
          {/* Stats */}
          <Card>
            <CardHeader className="px-4 py-3 pb-2">
              <CardTitle className="text-sm">Statistics</CardTitle>
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
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 pt-0 space-y-3">
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">All Channels</p>
                <div className="flex flex-col gap-2">
                  <Button
                    className="w-full justify-start"
                    onClick={() => fetchAll()}
                    disabled={loadingActions.has('fetch-all') || Object.keys(operations).length > 0}
                  >
                    <RefreshCw size={14} className="mr-2" />
                    {loadingActions.has('fetch-all') ? 'Fetching...' : Object.keys(operations).length > 0 ? 'Channel(s) processing...' : 'Fetch All'}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => analyzeAll()}
                    disabled={loadingActions.has('analyze-all') || Object.keys(operations).length > 0}
                  >
                    <Bot size={14} className="mr-2" />
                    {loadingActions.has('analyze-all') ? 'Analyzing...' : Object.keys(operations).length > 0 ? 'Channel(s) processing...' : 'Analyze All'}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => fetchAnalyzeAll()}
                    disabled={loadingActions.has('fetch-analyze-all') || Object.keys(operations).length > 0}
                  >
                    <Zap size={14} className="mr-2" />
                    {loadingActions.has('fetch-analyze-all') ? 'Processing...' : Object.keys(operations).length > 0 ? 'Channel(s) processing...' : 'Fetch + Analyze All'}
                  </Button>
                </div>
              </div>

              <Separator />

              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Cron Job</p>
                <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border mb-2">
                  <div className="flex items-center gap-2">
                    <Timer size={14} className={cronRunning ? 'text-green-500' : 'text-gray-400'} />
                    <span className="text-sm font-medium">{cronRunning ? 'Running' : 'Stopped'}</span>
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
                  {cronRunning ? 'Stop Cron Job' : 'Start Cron Job'}
                </Button>
              </div>

              <Separator />

              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">Other</p>
                <div className="flex flex-col gap-2">
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => reanalyzeSkipped()}
                    disabled={loadingActions.has('reanalyze-skipped')}
                  >
                    <RotateCcw size={14} className="mr-2" />
                    {loadingActions.has('reanalyze-skipped') ? 'Re-analyzing...' : 'Re-analyze Skipped'}
                  </Button>
                  <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={() => reanalyzeMessages()}
                    disabled={loadingActions.has('reanalyze')}
                  >
                    <RefreshCw size={14} className="mr-2" />
                    {loadingActions.has('reanalyze') ? 'Re-analyzing...' : 'Re-analyze Queued'}
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
                  Channels ({total})
                </CardTitle>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/channels" className="text-xs">Manage <ChevronRight size={12} className="inline" /></Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {initialLoading ? (
                <div className="px-4 py-8 text-center">
                  <Loader2 className="w-5 h-5 text-gray-400 animate-spin mx-auto mb-2" />
                  <p className="text-sm text-gray-500">Loading channels...</p>
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
                              {channel.is_active ? 'Active' : 'Inactive'}
                            </Badge>
                          </div>
                          {channel.name && <p className="text-xs text-gray-500 truncate">{channel.name}</p>}
                          <p className="text-xs text-gray-400 mt-0.5">
                            {(channel.message_count || 0).toLocaleString()} msgs &bull; {(channel.job_count || 0).toLocaleString()} jobs
                            {(channel.last_fetch_new_count || 0) > 0 && (
                              <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                +{channel.last_fetch_new_count} fetched
                              </span>
                            )}
                            {(channel.pending_count || 0) > 0 && (
                              <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                                {channel.pending_count} pending
                              </span>
                            )}
                          </p>
                          {channelProgress[channel.username] && (
                            <div className="mt-2">
                              <div className="flex justify-between text-xs mb-1">
                                <span className={stoppingChannels[channel.username] ? 'text-orange-600 font-medium' : ''}>
                                  {stoppingChannels[channel.username] ? '⚠ Stopping... (finishing current)' : 'Analyzing...'}
                                </span>
                                <span>{channelProgress[channel.username].current}/{channelProgress[channel.username].total}</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className={`h-2 rounded-full transition-all ${stoppingChannels[channel.username] ? 'bg-orange-500' : 'bg-blue-600'}`}
                                  style={{ width: `${(channelProgress[channel.username].current / channelProgress[channel.username].total) * 100}%` }}
                                />
                              </div>
                              {tokenUsage[channel.username] && (
                                <div className="flex justify-between text-xs mt-1 text-gray-500">
                                  <span>🤖 {(tokenUsage[channel.username].total / 1000).toFixed(1)}k tokens</span>
                                  <span>⬆{(tokenUsage[channel.username].input / 1000).toFixed(1)}k ⬇{(tokenUsage[channel.username].output / 1000).toFixed(1)}k</span>
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
                                {loadingActions.has(`fetch-${channel.id}`) ? 'Fetching...' : 'Fetch'}
                              </Button>
                              <Button
                                size="sm"
                                onClick={() => analyzeChannel(channel.id)}
                                disabled={loadingActions.has(`analyze-${channel.id}`)}
                              >
                                <Bot size={12} className="mr-1" />
                                {loadingActions.has(`analyze-${channel.id}`) ? 'Analyzing...' : 'Analyze'}
                              </Button>
                            </>
                          )}
                          {(loadingActions.has(`fetch-${channel.id}`) || loadingActions.has(`analyze-${channel.id}`) || !!operations[channel.username]) && (
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => stopAnalyzeChannel(channel.id, channel.username)}
                              title="Stop analysis"
                              disabled={stoppingChannels[channel.id] || stoppingChannels[channel.username]}
                            >
                              <Square size={12} className="mr-1" />
                              {stoppingChannels[channel.id] || stoppingChannels[channel.username] ? 'Stopping...' : 'Stop'}
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
                      Previous
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
                      Next
                    </Button>
                  </div>
                </>
              ) : (
                <div className="px-4 py-8 text-center">
                  <Radio size={32} className="text-gray-200 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">No channels configured.</p>
                  <Button asChild variant="outline" size="sm" className="mt-3">
                    <Link to="/channels">Add your first channel</Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
