import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Bot,
  Activity,
  Clock,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Zap,
  Globe,
  Radio,
  TrendingUp,
  Timer,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/components/Layout';
import api from '@/services/api';

interface AutonomousStatus {
  enabled: boolean;
  budget: {
    day?: string;
    total_tokens?: number;
  };
  sources_scored: number;
  fetches_24h: number;
  failures_24h: number;
}

interface SourceScoring {
  source_id: number;
  source_type: string;
  name: string;
  hourly_yield_24h: number;
  hourly_yield_7d: number;
  best_window_start: string | null;
  best_window_end: string | null;
  recommended_interval_minutes: number;
  consecutive_failures: number;
  last_optimized_at: string | null;
}

interface FetchOutcome {
  id: number;
  source_id: number | null;
  source_type: string;
  fetched_at: string;
  new_jobs_found: number;
  new_messages: number;
  duration_seconds: number | null;
  error_type: string | null;
  error_message: string | null;
}

interface DiscoveredSources {
  channels: Array<{
    id: number;
    username: string | null;
    name: string | null;
    description: string | null;
    created_at: string;
  }>;
  websites: Array<{
    id: number;
    name: string;
    url: string;
    site_type: string;
    extraction_prompt: string | null;
    created_at: string;
  }>;
}

const Autonomous = () => {
  const [status, setStatus] = useState<AutonomousStatus | null>(null);
  const [sources, setSources] = useState<SourceScoring[]>([]);
  const [outcomes, setOutcomes] = useState<FetchOutcome[]>([]);
  const [discovered, setDiscovered] = useState<DiscoveredSources | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { showToast } = useToast();
  const { t } = useTranslation();

  const loadData = async (isManual = false) => {
    if (isManual) setRefreshing(true);
    try {
      const [statusRes, sourcesRes, outcomesRes, discoveredRes] = await Promise.all([
        api.getAutonomousStatus(),
        api.getAutonomousSources(),
        api.getAutonomousOutcomes(20),
        api.getAutonomousDiscovered(),
      ]);
      setStatus(statusRes);
      setSources(sourcesRes);
      setOutcomes(outcomesRes);
      setDiscovered(discoveredRes);
    } catch (error: any) {
      if (isManual) showToast('error', `${t('autonomous.failedToLoad')}: ${error.message || t('common.unknown')}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => loadData(), 30000);
    return () => clearInterval(interval);
  }, []);

  const formatInterval = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    return `${Math.floor(minutes / 60)}h ${minutes % 60 > 0 ? ` ${minutes % 60}m` : ''}`;
  };

  const formatTime = (isoString: string | null) => {
    if (!isoString) return '—';
    return new Date(isoString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="w-9 h-9 rounded-lg" />
          <div className="space-y-1.5">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  const statCards = [
    {
      label: t('autonomous.scannerStatus'),
      value: status?.enabled ? t('autonomous.running') : t('autonomous.stopped'),
      icon: status?.enabled ? CheckCircle : AlertTriangle,
      iconColor: status?.enabled ? 'text-green-500' : 'text-yellow-500',
      bg: status?.enabled ? 'bg-green-50' : 'bg-yellow-50',
    },
    {
      label: t('autonomous.sourcesScored'),
      value: status?.sources_scored ?? 0,
      icon: Radio,
      iconColor: 'text-blue-500',
      bg: 'bg-blue-50',
    },
    {
      label: t('autonomous.fetches24h'),
      value: status?.fetches_24h ?? 0,
      icon: TrendingUp,
      iconColor: 'text-purple-500',
      bg: 'bg-purple-50',
    },
    {
      label: t('autonomous.failures24h'),
      value: status?.failures_24h ?? 0,
      icon: AlertTriangle,
      iconColor: (status?.failures_24h ?? 0) > 0 ? 'text-red-500' : 'text-muted-foreground',
      bg: (status?.failures_24h ?? 0) > 0 ? 'bg-red-50' : 'bg-muted',
    },
  ];

  return (
    <div className="space-y-5">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-slate-700 via-blue-800 to-indigo-800 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Bot className="w-5 h-5 text-blue-300" />
              <h1 className="text-xl font-bold tracking-tight">{t('autonomous.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{t('autonomous.subtitle')}</p>
          </div>
          <Button
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm w-full sm:w-auto"
            size="sm" onClick={() => loadData(true)} disabled={refreshing}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? 'animate-spin' : ''}`} />
            {t('autonomous.refresh')}
          </Button>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, iconColor, bg }) => (
          <Card key={label} className="shadow-sm">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center shrink-0`}>
                  <Icon className={`w-4 h-4 ${iconColor}`} />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground truncate">{label}</p>
                  <p className="text-xl font-bold leading-tight">{value}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Token Budget */}
      {status?.budget && (status.budget.day || status.budget.total_tokens) && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <div className="w-7 h-7 rounded-md bg-amber-100 flex items-center justify-center">
                <Zap className="w-4 h-4 text-amber-600" />
              </div>
              {t('autonomous.tokenBudget')}
            </CardTitle>
            <CardDescription className="text-xs">{t('autonomous.tokenBudgetDesc')}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-0.5">
                <p className="text-xs text-muted-foreground">{t('autonomous.period')}</p>
                <p className="text-lg font-semibold">{status.budget.day || '—'}</p>
              </div>
              <div className="space-y-0.5">
                <p className="text-xs text-muted-foreground">{t('autonomous.tokensUsed')}</p>
                <p className="text-lg font-semibold">{status.budget.total_tokens?.toLocaleString() ?? 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Source Schedule Optimization */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-blue-100 flex items-center justify-center">
              <Timer className="w-4 h-4 text-blue-600" />
            </div>
            {t('autonomous.sourceSchedule')}
          </CardTitle>
          <CardDescription className="text-xs">{t('autonomous.sourceScheduleDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {sources.length === 0 ? (
            <div className="py-12 text-center px-6">
              <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-3">
              <Clock size={20} className="text-muted-foreground opacity-50" />
            </div>
              <p className="text-sm text-muted-foreground">{t('autonomous.noSourcesScored')}</p>
              <p className="text-xs text-muted-foreground mt-1">{t('autonomous.noSourcesHint')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('autonomous.source')}</TableHead>
                  <TableHead>{t('autonomous.type')}</TableHead>
                  <TableHead className="text-right">{t('autonomous.yield24h')}</TableHead>
                  <TableHead className="text-right">{t('autonomous.yield7d')}</TableHead>
                  <TableHead>{t('autonomous.bestWindow')}</TableHead>
                  <TableHead>{t('autonomous.interval')}</TableHead>
                  <TableHead className="text-center">{t('autonomous.failures')}</TableHead>
                  <TableHead>{t('autonomous.lastOptimized')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sources.map((source) => (
                  <TableRow key={`${source.source_type}-${source.source_id}`}>
                    <TableCell className="font-medium">{source.name}</TableCell>
                    <TableCell>
                      <Badge variant={source.source_type === 'telegram' ? 'default' : 'secondary'} className="text-xs">
                        {source.source_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{source.hourly_yield_24h.toFixed(2)}</TableCell>
                    <TableCell className="text-right tabular-nums">{source.hourly_yield_7d.toFixed(2)}</TableCell>
                    <TableCell className="text-sm">
                      {source.best_window_start && source.best_window_end
                        ? `${source.best_window_start}–${source.best_window_end}`
                        : <span className="text-muted-foreground">—</span>}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs font-mono">{formatInterval(source.recommended_interval_minutes)}</Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {source.consecutive_failures > 0 ? (
                        <Badge variant="destructive" className="text-xs">{source.consecutive_failures}</Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{formatTime(source.last_optimized_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Fetch Outcomes */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-purple-100 flex items-center justify-center">
              <Activity className="w-4 h-4 text-purple-600" />
            </div>
            {t('autonomous.recentOutcomes')}
          </CardTitle>
          <CardDescription className="text-xs">{t('autonomous.recentOutcomesDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {outcomes.length === 0 ? (
            <div className="py-12 text-center px-6">
              <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-3">
              <Activity size={20} className="text-muted-foreground opacity-50" />
            </div>
              <p className="text-sm text-muted-foreground">{t('autonomous.noOutcomes')}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('autonomous.time')}</TableHead>
                  <TableHead>{t('autonomous.source')}</TableHead>
                  <TableHead>{t('autonomous.type')}</TableHead>
                  <TableHead className="text-right">{t('autonomous.jobs')}</TableHead>
                  <TableHead className="text-right">{t('autonomous.messages')}</TableHead>
                  <TableHead className="text-right">{t('autonomous.duration')}</TableHead>
                  <TableHead>{t('autonomous.status')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {outcomes.map((outcome) => (
                  <TableRow key={outcome.id}>
                    <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(outcome.fetched_at)}</TableCell>
                    <TableCell className="text-sm">{outcome.source_id ?? <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>
                      <Badge variant={outcome.source_type === 'telegram' ? 'default' : 'secondary'} className="text-xs">
                        {outcome.source_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{outcome.new_jobs_found}</TableCell>
                    <TableCell className="text-right tabular-nums text-sm">{outcome.new_messages}</TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">
                      {outcome.duration_seconds != null ? `${outcome.duration_seconds}s` : '—'}
                    </TableCell>
                    <TableCell>
                      {outcome.error_type ? (
                        <Badge variant="destructive" className="text-xs" title={outcome.error_message || ''}>
                          {outcome.error_type}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs border-green-300 text-green-700 bg-green-50">
                          <CheckCircle className="w-3 h-3 mr-1" />{t('autonomous.success')}
                        </Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Discovered Sources */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-green-100 flex items-center justify-center">
              <Globe className="w-4 h-4 text-green-600" />
            </div>
            {t('autonomous.discoveredSources')}
            <Badge variant="outline" className="text-xs ml-1">{t('autonomous.pendingApproval')}</Badge>
          </CardTitle>
          <CardDescription className="text-xs">{t('autonomous.discoveredSourcesDesc')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Telegram Channels */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Radio className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm font-medium">{t('autonomous.telegramChannels')}</span>
              <Badge variant="secondary" className="text-xs">{discovered?.channels.length ?? 0}</Badge>
            </div>
            {!discovered?.channels.length ? (
              <p className="text-sm text-muted-foreground pl-5">{t('autonomous.noDiscoveredChannels')}</p>
            ) : (
              <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('autonomous.username')}</TableHead>
                    <TableHead>{t('autonomous.name')}</TableHead>
                    <TableHead>{t('autonomous.description')}</TableHead>
                    <TableHead>{t('autonomous.discovered')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discovered.channels.map((channel) => (
                    <TableRow key={channel.id}>
                      <TableCell className="font-medium">{channel.username ?? '—'}</TableCell>
                      <TableCell>{channel.name ?? '—'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
                        {channel.description?.slice(0, 60) ?? '—'}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(channel.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>
            )}
          </div>

          <Separator />

          {/* Website Sources */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-3.5 h-3.5 text-muted-foreground" />
              <span className="text-sm font-medium">{t('autonomous.websiteSources')}</span>
              <Badge variant="secondary" className="text-xs">{discovered?.websites.length ?? 0}</Badge>
            </div>
            {!discovered?.websites.length ? (
              <p className="text-sm text-muted-foreground pl-5">{t('autonomous.noDiscoveredWebsites')}</p>
            ) : (
              <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t('autonomous.name')}</TableHead>
                    <TableHead>{t('autonomous.url')}</TableHead>
                    <TableHead>{t('autonomous.type')}</TableHead>
                    <TableHead>{t('autonomous.discovered')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discovered.websites.map((website) => (
                    <TableRow key={website.id}>
                      <TableCell className="font-medium">{website.name}</TableCell>
                      <TableCell className="text-xs text-muted-foreground max-w-[180px] truncate">{website.url}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">{website.site_type}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">{formatTime(website.created_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Autonomous;
