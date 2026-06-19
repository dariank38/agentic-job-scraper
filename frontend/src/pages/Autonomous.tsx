import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
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
} from 'lucide-react';
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

  const loadData = async () => {
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
    } catch (error) {
      console.error('Failed to load autonomous data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const formatInterval = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  };

  const formatTime = (isoString: string | null) => {
    if (!isoString) return '-';
    return new Date(isoString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Bot className="h-8 w-8" />
          Autonomous Dashboard
        </h1>
        <Button onClick={loadData} variant="outline" size="sm">
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {status?.enabled ? (
                <CheckCircle className="h-5 w-5 text-green-500" />
              ) : (
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
              )}
              <span className="text-2xl font-bold">
                {status?.enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Sources Scored</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Radio className="h-5 w-5 text-blue-500" />
              <span className="text-2xl font-bold">{status?.sources_scored || 0}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Fetches (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-purple-500" />
              <span className="text-2xl font-bold">{status?.fetches_24h || 0}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Failures (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-500" />
              <span className="text-2xl font-bold">{status?.failures_24h || 0}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Ollama Budget */}
      {status?.budget && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Ollama Token Budget
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Day</p>
                <p className="text-lg font-semibold">{status.budget.day || '-'}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Tokens Used</p>
                <p className="text-lg font-semibold">{status.budget.total_tokens?.toLocaleString() || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Source Scorings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Source Schedule Optimization
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Yield (24h)</TableHead>
                <TableHead>Yield (7d)</TableHead>
                <TableHead>Best Window</TableHead>
                <TableHead>Interval</TableHead>
                <TableHead>Failures</TableHead>
                <TableHead>Last Optimized</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sources.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground">
                    No sources scored yet
                  </TableCell>
                </TableRow>
              ) : (
                sources.map((source) => (
                  <TableRow key={`${source.source_type}-${source.source_id}`}>
                    <TableCell className="font-medium">{source.name}</TableCell>
                    <TableCell>
                      <Badge variant={source.source_type === 'telegram' ? 'default' : 'secondary'}>
                        {source.source_type}
                      </Badge>
                    </TableCell>
                    <TableCell>{source.hourly_yield_24h.toFixed(2)}</TableCell>
                    <TableCell>{source.hourly_yield_7d.toFixed(2)}</TableCell>
                    <TableCell>
                      {source.best_window_start && source.best_window_end
                        ? `${source.best_window_start} - ${source.best_window_end}`
                        : '-'}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{formatInterval(source.recommended_interval_minutes)}</Badge>
                    </TableCell>
                    <TableCell>
                      {source.consecutive_failures > 0 ? (
                        <Badge variant="destructive">{source.consecutive_failures}</Badge>
                      ) : (
                        <Badge variant="outline">{source.consecutive_failures}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatTime(source.last_optimized_at)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Recent Fetch Outcomes */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Fetch Outcomes
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Source ID</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Jobs</TableHead>
                <TableHead>Messages</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {outcomes.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    No fetch outcomes yet
                  </TableCell>
                </TableRow>
              ) : (
                outcomes.map((outcome) => (
                  <TableRow key={outcome.id}>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatTime(outcome.fetched_at)}
                    </TableCell>
                    <TableCell>{outcome.source_id || '-'}</TableCell>
                    <TableCell>
                      <Badge variant={outcome.source_type === 'telegram' ? 'default' : 'secondary'}>
                        {outcome.source_type}
                      </Badge>
                    </TableCell>
                    <TableCell>{outcome.new_jobs_found}</TableCell>
                    <TableCell>{outcome.new_messages}</TableCell>
                    <TableCell>{outcome.duration_seconds ? `${outcome.duration_seconds}s` : '-'}</TableCell>
                    <TableCell>
                      {outcome.error_type ? (
                        <Badge variant="destructive">{outcome.error_type}</Badge>
                      ) : (
                        <Badge variant="default">Success</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Discovered Sources */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Discovered Sources (Pending Approval)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Telegram Channels</h3>
            {discovered?.channels.length === 0 ? (
              <p className="text-sm text-muted-foreground">No discovered channels</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Username</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Discovered</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discovered?.channels.map((channel) => (
                    <TableRow key={channel.id}>
                      <TableCell className="font-medium">{channel.username || '-'}</TableCell>
                      <TableCell>{channel.name || '-'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {channel.description?.slice(0, 50) || '-'}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatTime(channel.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>

          <div>
            <h3 className="text-sm font-medium text-muted-foreground mb-2">Website Sources</h3>
            {discovered?.websites.length === 0 ? (
              <p className="text-sm text-muted-foreground">No discovered websites</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>URL</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Discovered</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {discovered?.websites.map((website) => (
                    <TableRow key={website.id}>
                      <TableCell className="font-medium">{website.name}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {website.url.slice(0, 40)}...
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{website.site_type}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatTime(website.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Autonomous;
