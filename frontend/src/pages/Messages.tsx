import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
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
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
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
  skip_reason?: string;
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
  job?: {
    id: number;
    title?: string;
    company?: string;
  };
  developer?: {
    id: number;
    name?: string;
  };
}

const Messages = () => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const [analyzingChannel, setAnalyzingChannel] = useState<string | null>(null);
  const [analysisProgress, setAnalysisProgress] = useState<{ processed: number; total: number } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [channels, setChannels] = useState<any[]>([]);
  const [websiteSources, setWebsiteSources] = useState<any[]>([]);
  const [reanalyzingId, setReanalyzingId] = useState<number | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [messageToDelete, setMessageToDelete] = useState<number | null>(null);
  const [expandedMessageId, setExpandedMessageId] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const limit = 8;
  const offset = parseInt(searchParams.get('offset') || '0');
  const { showToast } = useToast();

  const { progress: wsProgress } = useWebSocketProgress();

  useEffect(() => {
    loadChannelsAndSources();
  }, []);

  useEffect(() => {
    loadMessages();
  }, [searchParams, searchQuery, statusFilter, sourceFilter]);

  const loadChannelsAndSources = async () => {
    try {
      const [channelsData, sourcesData] = await Promise.all([
        api.getChannels({ limit: 1000 }),
        api.getWebsiteSources()
      ]);
      setChannels(channelsData.channels || []);
      setWebsiteSources(sourcesData.sources || []);
    } catch (e) {
      console.error('Failed to load channels/sources:', e);
    }
  };

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
      if (sourceFilter !== 'all') {
        if (sourceFilter.startsWith('channel-')) {
          params.channel_id = parseInt(sourceFilter.replace('channel-', ''));
        } else if (sourceFilter.startsWith('website-')) {
          params.website_source_id = parseInt(sourceFilter.replace('website-', ''));
        }
      }
      const data = await api.getMessages(params);
      setMessages(data.messages);
      setTotal(data.total);
    } catch (e: any) {
      let errorMessage = `${t('common.failedToLoad')} ${t('messages.title')}`;
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
      let errorMessage = `${t('common.failedToAnalyze')} ${t('messages.title')}`;
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

  const handleDeleteMessage = async () => {
    if (!messageToDelete) return;
    try {
      const data = await api.deleteMessage(messageToDelete);
      if (data.success) {
        showToast('success', t('messages.deletedSuccessfully'));
        loadMessages();
        setDeleteDialogOpen(false);
        setMessageToDelete(null);
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToDelete')} ${t('messages.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    }
  };

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'analyzed':
        return {
          label: t('messages.analyzed'),
          variant: 'default' as const,
          icon: CheckCircle2,
        };
      case 'skipped':
        return {
          label: t('messages.skipped'),
          variant: 'secondary' as const,
          icon: SkipForward,
        };
      case 'failed':
        return {
          label: t('messages.failed') || 'Failed',
          variant: 'destructive' as const,
          icon: Clock,
        };
      default:
        return {
          label: t('messages.pending'),
          variant: 'outline' as const,
          icon: Clock,
        };
    }
  };

  const getSourceInfo = (sourceType: string) => {
    switch (sourceType) {
      case 'telegram':
        return {
          icon: MessageSquare,
          label: 'Telegram',
        };
      case 'website':
        return {
          icon: MessageSquare,
          label: 'Website',
        };
      default:
        return {
          icon: MessageSquare,
          label: 'Unknown',
        };
    }
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {t('messages.title')}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {total} {t('messages.totalMessages')}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" onClick={loadMessages} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Analysis Progress */}
      {analyzingChannel && (
        <Card className="mb-6">
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin" />
              <div className="flex-1">
                <p className="font-semibold">
                  {t('messages.analyzingChannel', { channel: analyzingChannel })}
                </p>
                {analysisProgress && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="font-medium">{t('messages.processingMessages')}</span>
                      <span className="font-bold">{analysisProgress.processed} / {analysisProgress.total}</span>
                    </div>
                    <div className="w-full bg-secondary rounded-full h-2.5 overflow-hidden">
                      <div
                        className="bg-primary h-2.5 rounded-full transition-all duration-300 ease-out"
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
      <Card className="mb-6">
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('messages.searchPlaceholder')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { setSearchParams({}); setSearchQuery(searchInput); } }}
                className="pl-9"
              />
            </div>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-3 py-2 rounded-md border text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring w-full sm:w-auto"
            >
              <option value="all">{t('messages.allSources') || 'All Sources'}</option>
              <optgroup label={t('common.channels') || 'Channels'}>
                {channels.map((ch: any) => (
                  <option key={`channel-${ch.id}`} value={`channel-${ch.id}`}>
                    {ch.username || ch.name}
                  </option>
                ))}
              </optgroup>
              <optgroup label={t('common.websiteSources') || 'Website Sources'}>
                {websiteSources.map((ws: any) => (
                  <option key={`website-${ws.id}`} value={`website-${ws.id}`}>
                    {ws.name}
                  </option>
                ))}
              </optgroup>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 rounded-md border text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring w-full sm:w-auto"
            >
              <option value="all">{t('messages.allStatus')}</option>
              <option value="analyzed">{t('messages.analyzed')}</option>
              <option value="pending">{t('messages.pending')}</option>
              <option value="skipped">{t('messages.skipped')}</option>
              <option value="failed">{t('messages.failed') || 'Failed'}</option>
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
              const sourceInfo = getSourceInfo(msg.source_type);
              const SourceIcon = sourceInfo.icon;
              return (
                <Card
                  key={msg.id}
                  className="cursor-pointer hover:bg-muted/50 transition-colors"
                  onClick={() => setExpandedMessageId(expandedMessageId === msg.id ? null : msg.id)}
                >
                  <CardContent className="py-4">
                    <div className="flex items-start gap-4">
                      {/* Icon */}
                      <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center shrink-0">
                        <SourceIcon className="w-5 h-5 text-muted-foreground" />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2 flex-wrap">
                          <span className="font-semibold text-sm truncate">
                            {msg.source_type === 'website' ? msg.website_source?.name : msg.channel?.username || t('common.unknown')}
                          </span>
                          <Badge variant={statusInfo.variant} className="text-xs">
                            <StatusIcon className="w-3 h-3 mr-1" />
                            {statusInfo.label}
                          </Badge>
                          {msg.has_image && (
                            <Badge variant="outline" className="text-xs">
                              <ImageIcon className="w-3 h-3 mr-1" />
                              {t('messages.image')}
                            </Badge>
                          )}
                          {msg.job && (
                            <Button
                              variant="outline"
                              size="sm"
                              asChild
                              className="text-xs h-7 px-2"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <a href={`/jobs?jobId=${msg.job.id}`}>
                                {t('messages.viewJob')}
                              </a>
                            </Button>
                          )}
                          {msg.developer && (
                            <Button
                              variant="outline"
                              size="sm"
                              asChild
                              className="text-xs h-7 px-2"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <a href={`/developers?developerId=${msg.developer.id}`}>
                                {t('messages.viewDeveloper')}
                              </a>
                            </Button>
                          )}
                          {msg.analysis_status === 'skipped' && (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); reanalyzeSingle(msg.id); }}
                                disabled={reanalyzingId === msg.id}
                                className="text-xs h-7 px-2"
                              >
                                {reanalyzingId === msg.id ? (
                                  <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                ) : (
                                  <RotateCcw className="w-3 h-3 mr-1" />
                                )}
                                {t('messages.reanalyze')}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => { e.stopPropagation(); setMessageToDelete(msg.id); setDeleteDialogOpen(true); }}
                                className="text-xs h-7 px-2 text-destructive hover:text-destructive"
                              >
                                {t('common.delete')}
                              </Button>
                            </>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              const text = msg.text?.replace(/<[^>]*>/g, '') || '';
                              navigator.clipboard.writeText(text);
                              setCopiedId(msg.id);
                              setTimeout(() => setCopiedId(null), 2000);
                            }}
                            className="text-xs h-7 px-2"
                          >
                            {copiedId === msg.id ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => { e.stopPropagation(); setExpandedMessageId(expandedMessageId === msg.id ? null : msg.id); }}
                            className="text-xs h-7 px-2 ml-auto sm:ml-0"
                          >
                            {expandedMessageId === msg.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          </Button>
                        </div>

                        <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {msg.date ? new Date(msg.date).toLocaleString() : t('common.unknown')}
                          </span>
                          {(msg.sender_username || msg.sender_first_name) && (
                            <span className="flex items-center gap-1">
                              <User className="w-3 h-3" />
                              {msg.sender_username || msg.sender_first_name}
                            </span>
                          )}
                        </div>

                        {expandedMessageId === msg.id ? (
                          <div
                            className="text-sm text-muted-foreground leading-relaxed"
                            dangerouslySetInnerHTML={{ __html: msg.text || '<No text content>' }}
                          />
                        ) : (
                          <div
                            className="text-sm text-muted-foreground line-clamp-2 leading-relaxed"
                            dangerouslySetInnerHTML={{ __html: msg.text || '<No text content>' }}
                          />
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Pagination */}
          <div className="flex justify-center gap-3 mt-8">
            <Button
              onClick={handlePrevious}
              disabled={offset === 0}
              variant="outline"
              size="sm"
            >
              {t('common.previous')}
            </Button>
            <span className="flex items-center text-sm text-muted-foreground font-medium px-3">
              {offset + 1}-{Math.min(offset + limit, total)} / {total}
            </span>
            <Button
              onClick={handleNext}
              disabled={offset + limit >= total}
              variant="outline"
              size="sm"
            >
              {t('common.next')}
            </Button>
          </div>
        </>
      ) : (
        <Card>
          <CardContent className="pt-16 pb-16 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-muted flex items-center justify-center">
              <MessageSquare className="w-8 h-8 text-muted-foreground" />
            </div>
            <p className="text-muted-foreground mb-2 font-semibold text-lg">{t('messages.noMessages')}</p>
            <p className="text-sm text-muted-foreground mb-6">{t('messages.fetchHint')}</p>
            <Button asChild variant="outline">
              <a href="/channels">{t('messages.goToChannels')}</a>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('messages.deleteConfirm')}</DialogTitle>
            <DialogDescription>
              {t('messages.deleteWarning')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleDeleteMessage}>
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </>
  );
};

export default Messages;
