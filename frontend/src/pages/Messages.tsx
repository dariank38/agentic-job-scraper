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
        api.getChannels(),
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
          color: 'text-emerald-700 bg-emerald-50 border-emerald-200'
        };
      case 'skipped':
        return {
          label: t('messages.skipped'),
          variant: 'secondary' as const,
          icon: SkipForward,
          color: 'text-slate-600 bg-slate-50 border-slate-200'
        };
      case 'failed':
        return {
          label: t('messages.failed') || 'Failed',
          variant: 'destructive' as const,
          icon: Clock,
          color: 'text-red-700 bg-red-50 border-red-200'
        };
      default:
        return {
          label: t('messages.pending'),
          variant: 'outline' as const,
          icon: Clock,
          color: 'text-amber-700 bg-amber-50 border-amber-200'
        };
    }
  };

  const getSourceInfo = (sourceType: string) => {
    switch (sourceType) {
      case 'telegram':
        return {
          gradient: 'from-blue-500 to-cyan-500',
          icon: 'TG',
          color: 'text-blue-600 bg-blue-50 border-blue-200'
        };
      case 'website':
        return {
          gradient: 'from-purple-500 to-pink-500',
          icon: 'WS',
          color: 'text-purple-600 bg-purple-50 border-purple-200'
        };
      default:
        return {
          gradient: 'from-gray-500 to-gray-600',
          icon: '?',
          color: 'text-gray-600 bg-gray-50 border-gray-200'
        };
    }
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            {t('messages.title')}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {total} {t('messages.totalMessages')}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" onClick={loadMessages} disabled={loading} className="shadow-sm">
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Analysis Progress */}
      {analyzingChannel && (
        <Card className="mb-6 border-2 border-blue-200 bg-gradient-to-r from-blue-50 to-cyan-50 shadow-sm">
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
              <div className="flex-1">
                <p className="font-semibold text-blue-900">
                  {t('messages.analyzingChannel', { channel: analyzingChannel })}
                </p>
                {analysisProgress && (
                  <div className="mt-2">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-blue-700 font-medium">{t('messages.processingMessages')}</span>
                      <span className="text-blue-700 font-bold">{analysisProgress.processed} / {analysisProgress.total}</span>
                    </div>
                    <div className="w-full bg-blue-200 rounded-full h-2.5 overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-cyan-500 h-2.5 rounded-full transition-all duration-300 ease-out"
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
      <Card className="mb-6 shadow-sm border-slate-200">
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                placeholder={t('messages.searchPlaceholder')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { setSearchParams({}); setSearchQuery(searchInput); } }}
                className="pl-9 border-slate-200 focus:border-blue-400"
              />
            </div>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="px-3 py-2 rounded-md border border-slate-200 text-sm bg-white focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
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
              className="px-3 py-2 rounded-md border border-slate-200 text-sm bg-white focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
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
          <div className="space-y-4">
            {messages.map((msg) => {
              const statusInfo = getStatusInfo(msg.analysis_status);
              const StatusIcon = statusInfo.icon;
              const sourceInfo = getSourceInfo(msg.source_type);
              return (
                <details key={msg.id} className="group">
                  <summary className="list-none cursor-pointer">
                    <Card className="transition-all hover:shadow-lg border-slate-200 hover:border-blue-300">
                      <CardContent className="py-4">
                        <div className="flex items-start gap-4">
                          {/* Avatar */}
                          <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${sourceInfo.gradient} flex items-center justify-center text-sm font-bold text-white shrink-0 shadow-md`}>
                            {sourceInfo.icon}
                          </div>

                          {/* Content */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                              <span className="font-semibold text-sm text-slate-900 truncate">
                                {msg.source_type === 'website' ? msg.website_source?.name : msg.channel?.username || t('common.unknown')}
                              </span>
                              <Badge variant={statusInfo.variant} className={`text-xs px-2.5 py-0.5 ${statusInfo.color}`}>
                                <StatusIcon className="w-3 h-3 mr-1" />
                                {statusInfo.label}
                              </Badge>
                              {msg.has_image && (
                                <Badge variant="outline" className="text-xs px-2 py-0.5 border-slate-300">
                                  <ImageIcon className="w-3 h-3 mr-1" />
                                  {t('messages.image')}
                                </Badge>
                              )}
                              {msg.job && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  asChild
                                  className="text-xs h-7 px-2.5 border-slate-300 hover:border-blue-400"
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
                                  className="text-xs h-7 px-2.5 border-slate-300 hover:border-blue-400"
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
                                    className="text-xs h-7 px-2.5 text-slate-600 hover:text-slate-900 hover:bg-slate-100"
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
                                    className="text-xs h-7 px-2.5 text-red-600 hover:text-red-700 hover:bg-red-50"
                                  >
                                    {t('common.delete')}
                                  </Button>
                                </>
                              )}
                            </div>

                            <div className="flex items-center gap-3 text-xs text-slate-500 mb-2">
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

                            <div
                              className="text-sm text-slate-600 line-clamp-2 leading-relaxed"
                              dangerouslySetInnerHTML={{ __html: msg.text || '<No text content>' }}
                            />
                          </div>

                          <ChevronDown className="w-5 h-5 text-slate-400 transition-transform group-open:rotate-180 shrink-0 mt-1" />
                        </div>
                      </CardContent>
                    </Card>
                  </summary>
                  <Card className="mt-2 bg-slate-50 border-slate-200">
                    <CardContent className="pt-4">
                      {msg.skip_reason && (
                        <div className="mb-3 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                          <div className="flex items-center gap-2 text-xs text-amber-800">
                            <SkipForward className="w-3.5 h-3.5" />
                            <span className="font-medium">{t('messages.skipReason')}:</span>
                            <span>{msg.skip_reason}</span>
                          </div>
                        </div>
                      )}
                      <div className="flex items-center gap-2 mb-3 text-xs text-slate-500 font-medium">
                        <MessageSquare className="w-3.5 h-3.5" />
                        <span>{t('messages.fullMessage')}</span>
                      </div>
                      <div
                        className="text-sm leading-relaxed break-words text-slate-700"
                        dangerouslySetInnerHTML={{ __html: msg.text || '<No text content>' }}
                      />
                    </CardContent>
                  </Card>
                </details>
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
              className="shadow-sm border-slate-300"
            >
              {t('common.previous')}
            </Button>
            <span className="flex items-center text-sm text-slate-600 font-medium px-3">
              {offset + 1}-{Math.min(offset + limit, total)} / {total}
            </span>
            <Button
              onClick={handleNext}
              disabled={offset + limit >= total}
              variant="outline"
              size="sm"
              className="shadow-sm border-slate-300"
            >
              {t('common.next')}
            </Button>
          </div>
        </>
      ) : (
        <Card className="border-slate-200 shadow-sm">
          <CardContent className="pt-16 pb-16 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center">
              <MessageSquare className="w-8 h-8 text-slate-400" />
            </div>
            <p className="text-slate-600 mb-2 font-semibold text-lg">{t('messages.noMessages')}</p>
            <p className="text-sm text-slate-500 mb-6">{t('messages.fetchHint')}</p>
            <Button asChild variant="outline" className="shadow-sm border-slate-300">
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
