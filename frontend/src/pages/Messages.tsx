import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ChevronDown,
  Loader2,
  MessageSquare,
  Calendar,
  User,
  RefreshCw,
  Image as ImageIcon,
  CheckCircle2,
  Clock,
  SkipForward,
  Search,
  RotateCcw,
} from 'lucide-react';
import api from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

interface Message {
  id: number;
  telegram_id: number;
  channel_id: number;
  date: string;
  text: string;
  sender_username?: string;
  sender_first_name?: string;
  has_image: boolean;
  analysis_status: string;
  source_type: string;
  channel?: {
    id: number;
    username: string;
    name?: string;
  };
  website_source?: {
    id: number;
    name: string;
    url: string;
  };
}

const Messages = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [analyzingChannel, setAnalyzingChannel] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<{ processed: number; total: number } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [reanalyzingId, setReanalyzingId] = useState<number | null>(null);
  const limit = 8;
  const offset = parseInt(searchParams.get('offset') || '0');
  const { showToast } = useToast();

  const { progress: wsProgress } = useWebSocketProgress();

  useEffect(() => {
    loadMessages();
  }, [searchParams, searchQuery, statusFilter]);

  useEffect(() => {
    if (wsProgress) {
      if (wsProgress.type === 'analyze_start') {
        setAnalyzingChannel(wsProgress.channel || null);
        setAnalysisProgress(null);
      } else if (wsProgress.type === 'analyze_progress') {
        setAnalysisProgress({
          processed: wsProgress.processed || 0,
          total: wsProgress.total || 0,
        });
      } else if (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error') {
        setAnalyzingChannel(null);
        setAnalysisProgress(null);
        loadMessages();
      }
    }
  }, [wsProgress]);

  const loadMessages = async () => {
    setLoading(true);
    try {
      const params: any = { limit, offset };
      if (searchQuery) params.search = searchQuery;
      if (statusFilter !== 'all') params.analysis_status = statusFilter;
      const data = await api.getMessages(params);
      setMessages(data.messages);
      setTotal(data.total);
    } catch (e: any) {
      let errorMessage = 'Failed to load messages';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    } finally {
      setLoading(false);
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

  const reanalyzeSingle = async (messageId: number) => {
    setReanalyzingId(messageId);
    try {
      const data = await api.reanalyzeMessage(messageId);
      if (data.success) {
        loadMessages();
      }
    } catch (e: any) {
      let errorMessage = 'Failed to re-analyze message';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    } finally {
      setReanalyzingId(null);
    }
  };

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'analyzed': 
        return { 
          label: 'Analyzed', 
          variant: 'default' as const,
          icon: CheckCircle2,
          color: 'text-green-600 bg-green-100'
        };
      case 'skipped': 
        return { 
          label: 'Skipped', 
          variant: 'secondary' as const,
          icon: SkipForward,
          color: 'text-gray-600 bg-gray-100'
        };
      default: 
        return { 
          label: 'Pending', 
          variant: 'outline' as const,
          icon: Clock,
          color: 'text-yellow-600 bg-yellow-100'
        };
    }
  };

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Messages</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total} message{total !== 1 ? 's' : ''} total
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" onClick={loadMessages} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Analysis Progress */}
      {analyzingChannel && (
        <Card className="mb-4 border-blue-200 bg-blue-50">
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
              <div className="flex-1">
                <p className="font-medium text-blue-900">
                  Analyzing {analyzingChannel}
                </p>
                {analysisProgress && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-blue-700">Processing messages...</span>
                      <span className="text-blue-700">{analysisProgress.processed} / {analysisProgress.total}</span>
                    </div>
                    <div className="w-full bg-blue-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all"
                        style={{ width: `${(analysisProgress.processed / analysisProgress.total) * 100}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card className="mb-4">
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search messages..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
            >
              <option value="all">All Status</option>
              <option value="analyzed">Analyzed</option>
              <option value="pending">Pending</option>
              <option value="skipped">Skipped</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Messages List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="py-4">
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : messages.length > 0 ? (
        <>
          <div className="space-y-3">
            {messages.map((msg) => {
              const statusInfo = getStatusInfo(msg.analysis_status);
              const StatusIcon = statusInfo.icon;
              return (
                <details key={msg.id} className="group">
                  <summary className="list-none cursor-pointer">
                    <Card className="transition-all hover:shadow-md border border-gray-200">
                      <CardContent className="py-4">
                        <div className="flex items-start gap-3">
                          {/* Avatar */}
                          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-sm font-bold text-white shrink-0">
                            {getInitials(msg.source_type === 'website' ? msg.website_source?.name || 'WS' : msg.channel?.username || 'CH')}
                          </div>
                          
                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                              <span className="font-semibold text-sm text-gray-900 truncate">
                                {msg.source_type === 'website' ? msg.website_source?.name : msg.channel?.username || 'unknown'}
                              </span>
                              <Badge variant={statusInfo.variant} className="text-xs px-2 py-0.5">
                                <StatusIcon className="w-3 h-3 mr-1" />
                                {statusInfo.label}
                              </Badge>
                              {msg.has_image && (
                                <Badge variant="outline" className="text-xs px-2 py-0.5">
                                  <ImageIcon className="w-3 h-3 mr-1" />
                                  Image
                                </Badge>
                              )}
                              {msg.analysis_status === 'skipped' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={(e) => { e.stopPropagation(); reanalyzeSingle(msg.id); }}
                                  disabled={reanalyzingId === msg.id}
                                  className="text-xs h-6 px-2"
                                >
                                  {reanalyzingId === msg.id ? (
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                  ) : (
                                    <RotateCcw className="w-3 h-3 mr-1" />
                                  )}
                                  Re-analyze
                                </Button>
                              )}
                            </div>
                            
                            <div className="flex items-center gap-3 text-xs text-gray-500 mb-1.5">
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3 h-3" />
                                {msg.date ? new Date(msg.date).toLocaleString() : 'Unknown'}
                              </span>
                              {(msg.sender_username || msg.sender_first_name) && (
                                <span className="flex items-center gap-1">
                                  <User className="w-3 h-3" />
                                  {msg.sender_username || msg.sender_first_name}
                                </span>
                              )}
                            </div>
                            
                            <div
                              className="text-sm text-gray-600 line-clamp-2"
                              dangerouslySetInnerHTML={{ __html: msg.text || '<No text content>' }}
                            />
                          </div>
                          
                          <ChevronDown className="w-5 h-5 text-gray-400 transition-transform group-open:rotate-180 shrink-0 mt-1" />
                        </div>
                      </CardContent>
                    </Card>
                  </summary>
                  <Card className="mt-2 bg-gray-50">
                    <CardContent className="pt-4">
                      <div className="flex items-center gap-2 mb-3 text-xs text-gray-500">
                        <MessageSquare className="w-3.5 h-3.5" />
                        <span>Full Message</span>
                      </div>
                      <div
                        className="text-sm leading-relaxed break-words"
                        dangerouslySetInnerHTML={{ __html: msg.text || '<No text content>' }}
                      />
                    </CardContent>
                  </Card>
                </details>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="flex justify-center gap-3 mt-6">
            <Button
              onClick={handlePrevious}
              disabled={offset === 0}
              variant="outline"
              size="sm"
            >
              Previous
            </Button>
            <span className="flex items-center text-sm text-gray-500">
              {offset + 1}-{Math.min(offset + limit, total)} of {total}
            </span>
            <Button
              onClick={handleNext}
              disabled={offset + limit >= total}
              variant="outline"
              size="sm"
            >
              Next
            </Button>
          </div>
        </>
      ) : (
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <MessageSquare className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-gray-500 mb-1 font-medium">No messages found</p>
            <p className="text-sm text-gray-400 mb-4">Try fetching from channels first to see messages.</p>
            <Button asChild variant="outline">
              <a href="/channels">Go to Channels</a>
            </Button>
          </CardContent>
        </Card>
      )}
    </>
  );
};

export default Messages;
