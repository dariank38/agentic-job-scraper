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
  ChevronRight,
  Loader2,
  Zap,
} from 'lucide-react';
import api from '@/services/api';
import type { Channel, Stats } from '@/services/api';
import { useWebSocketProgress } from '@/components/Layout';

const Dashboard = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [status, setStatus] = useState<{ message: string; isError: boolean } | null>(null);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const [cronRunning, setCronRunning] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [searchParams, setSearchParams] = useSearchParams();
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');

  const { progress: wsProgress, channelProgress, operations } = useWebSocketProgress();

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
      console.error('Failed to load data:', error);
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

  const showStatus = (message: string, isError = false) => {
    setStatus({ message, isError });
    setTimeout(() => setStatus(null), 5000);
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
        showStatus(`Fetched ${data.new_messages} new messages from channel (${data.days_back_used}d window)`);
        loadData();
      } else {
        showStatus('Error: ' + (data.error || 'Unknown'), true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const analyzeChannel = async (channelId: number) => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showStatus('Error: Ollama is not available. Please check if Ollama is running.', true);
        return;
      }

      const data = await withLoading(`analyze-${channelId}`, () => api.analyzeChannel(channelId));
      if (data.success) {
        if (data.stopped) {
          showStatus(`Stopped! Analyzed ${data.analyzed} msgs, ${data.jobs_found} jobs (${data.remaining} remaining)`);
        } else {
          showStatus(`Analyzed: ${data.analyzed} msgs, ${data.jobs_found} jobs, ${data.developers_found} devs`);
        }
        setTimeout(() => loadData(), 1500);
      } else {
        showStatus('Error: ' + (data.error || 'Unknown'), true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const stopAnalyzeChannel = async () => {
    try {
      const data = await api.stopAnalyze();
      if (data.success) {
        showStatus('Stop signal sent');
      } else {
        showStatus('Error stopping analysis', true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const checkCronStatus = async () => {
    try {
      const data = await api.getCronStatus();
      if (data.success) {
        setCronRunning(data.running);
      }
    } catch (error) {
      console.error('Failed to check cron status:', error);
    }
  };

  const toggleCron = async () => {
    try {
      if (cronRunning) {
        const data = await api.stopCron();
        if (data.success) {
          setCronRunning(false);
          showStatus('Cron job stopped');
        } else {
          showStatus('Error: ' + (data.message || 'Unknown'), true);
        }
      } else {
        const data = await api.startCron();
        if (data.success) {
          setCronRunning(true);
          showStatus('Cron job started - fetching messages every 30 minutes');
        } else {
          showStatus('Error: ' + (data.message || 'Unknown'), true);
        }
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const fetchAll = async () => {
    try {
      const data = await withLoading('fetch-all', () => api.fetchAll());
      if (data.success) {
        const total = data.results.reduce((s: number, r: any) => s + (r.new_messages || 0), 0);
        showStatus(`Fetched ${total} new messages across all channels`);
      } else {
        showStatus('Error: ' + (data.error || 'Unknown'), true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const analyzeAll = async () => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showStatus('Error: Ollama is not available. Please check if Ollama is running.', true);
        return;
      }

      const data = await withLoading('analyze-all', () => api.analyzeAll());
      if (data.success) {
        const totalJobs = data.results.reduce((s: number, r: any) => s + (r.jobs_found || 0), 0);
        const wasStopped = data.results.some((r: any) => r.stopped);
        if (wasStopped) {
          showStatus(`Stopped! Found ${totalJobs} jobs across channels (some remaining)`);
        } else {
          showStatus(`Analysis complete! Found ${totalJobs} jobs across all channels`);
        }
        setTimeout(() => loadData(), 1500);
      } else {
        showStatus('Error: ' + (data.error || 'Unknown'), true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const searchAll = async () => {
    try {
      // Check if Ollama is available before attempting analysis (search includes analysis)
      if (!stats?.ollama_available) {
        showStatus('Error: Ollama is not available. Please check if Ollama is running.', true);
        return;
      }

      const data = await withLoading('search-all', () => api.searchAll());
      if (data.success) {
        const totalJobs = data.results.reduce((s: number, r: any) => s + (r.total_jobs || 0), 0);
        showStatus(`Complete! Found ${totalJobs} jobs across all channels`);
        setTimeout(() => loadData(), 2000);
      } else {
        showStatus('Error: ' + (data.error || 'Unknown'), true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
    }
  };

  const reanalyzeMessages = async () => {
    try {
      // Check if Ollama is available before attempting analysis
      if (!stats?.ollama_available) {
        showStatus('Error: Ollama is not available. Please check if Ollama is running.', true);
        return;
      }

      const data = await withLoading('reanalyze', () => api.reanalyzeMessages());
      if (data.success) {
        showStatus(`Re-analysis complete! Processed ${data.reanalyzed} messages`);
        setTimeout(() => loadData(), 1500);
      } else {
        showStatus('Error: ' + (data.error || 'Unknown'), true);
      }
    } catch (e: any) {
      showStatus('Error: ' + e.message, true);
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
      {/* Stats Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {statItems.map(({ icon: Icon, value, label, color }) => (
          <Card key={label} className="hover:shadow-md transition-shadow">
            <CardContent>
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-0.5">{label}</p>
                  <p className="text-xl font-bold">{value}</p>
                </div>
                <div className={`p-1.5 rounded-md ${color}`}>
                  <Icon size={14} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions */}
        <div className="lg:col-span-1 space-y-4">
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
                    onClick={() => searchAll()}
                    disabled={loadingActions.has('search-all') || Object.keys(operations).length > 0}
                  >
                    <Zap size={14} className="mr-2" />
                    {loadingActions.has('search-all') ? 'Processing...' : Object.keys(operations).length > 0 ? 'Channel(s) processing...' : 'Fetch + Analyze All'}
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
                    onClick={() => reanalyzeMessages()}
                    disabled={loadingActions.has('reanalyze')}
                  >
                    <RefreshCw size={14} className="mr-2" />
                    {loadingActions.has('reanalyze') ? 'Re-analyzing...' : 'Re-analyze Queued'}
                  </Button>
                </div>
              </div>

              {status && (
                <div className={`p-3 rounded-md text-sm ${status.isError ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
                  {status.message}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Navigate */}
          <Card>
            <CardHeader className="px-4 py-3 pb-2">
              <CardTitle className="text-sm">Navigate</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {[
                { to: '/channels', label: 'Manage Channels', icon: Radio },
                { to: '/messages', label: 'View Messages', icon: MessageSquare },
                { to: '/jobs', label: 'View Jobs', icon: Briefcase },
                { to: '/developers', label: 'View Developers', icon: Users },
              ].map(({ to, label, icon: Icon }) => (
                <Link
                  key={to}
                  to={to}
                  className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors no-underline text-gray-700 border-b last:border-b-0"
                >
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Icon size={15} className="text-gray-400" />
                    {label}
                  </div>
                  <ChevronRight size={14} className="text-gray-300" />
                </Link>
              ))}
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
                                <span>Analyzing...</span>
                                <span>{channelProgress[channel.username].current}/{channelProgress[channel.username].total}</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div
                                  className="bg-blue-600 h-2 rounded-full transition-all"
                                  style={{ width: `${(channelProgress[channel.username].current / channelProgress[channel.username].total) * 100}%` }}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                        <div className="flex gap-2 flex-shrink-0">
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
                          {loadingActions.has(`analyze-${channel.id}`) && (
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => stopAnalyzeChannel()}
                            >
                              <Square size={12} />
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
