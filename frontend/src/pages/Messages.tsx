import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Checkbox } from '@/components/ui/checkbox';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select';
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
  RefreshCw,
  CheckCircle2,
  Clock,
  SkipForward,
  Search,
  RotateCcw,
  Copy,
  Check,
  Ban,
  Trash2,
  Briefcase,
  Code2,
  ExternalLink,
  Globe,
  User,
  Calendar,
  Image as ImageIcon,
  ScrollText,
} from 'lucide-react';
import api from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';
import { copyToClipboard } from '@/utils/clipboard';

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
  is_manual_skip: boolean;
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
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [selectedMessageIds, setSelectedMessageIds] = useState<Set<number>>(new Set());
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [togglingSkipId, setTogglingSkipId] = useState<number | null>(null);
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

  const navigate = useNavigate();

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

  const handleToggleSkip = async (messageId: number) => {
    setTogglingSkipId(messageId);
    try {
      const data = await api.toggleSkipMessage(messageId);
      if (data.success) {
        showToast('success', data.is_manual_skip ? t('messages.markedSkipped') : t('messages.unmarkedSkipped'));
        setMessages(prev => prev.map(m => m.id === messageId ? { ...m, is_manual_skip: data.is_manual_skip, analysis_status: data.analysis_status, skip_reason: data.is_manual_skip ? 'manual' : undefined } : m));
        if (selectedMessage && selectedMessage.id === messageId) {
          setSelectedMessage({ ...selectedMessage, is_manual_skip: data.is_manual_skip, analysis_status: data.analysis_status, skip_reason: data.is_manual_skip ? 'manual' : undefined });
        }
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToUpdate')} ${t('messages.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    } finally {
      setTogglingSkipId(null);
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

  const toggleMessageSelection = (id: number) => {
    setSelectedMessageIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllMessages = () => {
    const allIds = new Set(messages.map(m => m.id));
    setSelectedMessageIds(allIds);
  };

  const clearMessageSelection = () => {
    setSelectedMessageIds(new Set());
  };

  const handleBulkDeleteMessages = async () => {
    if (selectedMessageIds.size === 0) return;
    try {
      const data = await api.bulkDeleteMessages(Array.from(selectedMessageIds));
      if (data.success) {
        showToast('success', t('messages.bulkDeletedSuccessfully', { count: data.deleted }));
        setSelectedMessageIds(new Set());
        setBulkDeleteDialogOpen(false);
        loadMessages();
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
          label: t('messages.failed'),
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
          label: t('common.telegram'),
        };
      case 'website':
        return {
          icon: MessageSquare,
          label: t('common.website'),
        };
      default:
        return {
          icon: MessageSquare,
          label: t('common.unknown'),
        };
    }
  };

  return (
    <>
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl mb-5 bg-gradient-to-br from-violet-600 via-purple-600 to-pink-600 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <MessageSquare className="w-5 h-5" />
              <h1 className="text-xl font-bold tracking-tight">{t('messages.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{total} {t('messages.totalMessages')}</p>
          </div>
          <Button
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm w-full sm:w-auto"
            size="sm" onClick={loadMessages} disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </Button>
        </div>
      </div>

      {/* Analysis Progress */}
      {analyzingChannel && (
        <Card className="mb-4 border-violet-200 bg-gradient-to-r from-violet-50 to-purple-50">
          <CardContent className="py-4">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-violet-500" />
              <div className="flex-1">
                <p className="font-semibold text-sm text-violet-900">
                  {t('messages.analyzingChannel', { channel: analyzingChannel })}
                </p>
                {analysisProgress && (
                  <div className="mt-2 space-y-1">
                    <div className="flex justify-between text-xs text-violet-700">
                      <span>{t('messages.processingMessages')}</span>
                      <span className="font-bold">{analysisProgress.processed} / {analysisProgress.total}</span>
                    </div>
                    <div className="w-full bg-violet-100 rounded-full h-1.5 overflow-hidden">
                      <div
                        className="bg-violet-500 h-1.5 rounded-full transition-all duration-300 ease-out"
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
      <Card className="mb-4 shadow-sm">
        <CardContent className="pt-3 pb-3">
          <div className="flex flex-col sm:flex-row gap-2">
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
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-full sm:w-48 h-9 text-sm">
                <SelectValue placeholder={t('messages.allSources')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('messages.allSources')}</SelectItem>
                <SelectGroup>
                  <SelectLabel>{t('common.channels')}</SelectLabel>
                  {channels.map((ch: any) => (
                    <SelectItem key={`channel-${ch.id}`} value={`channel-${ch.id}`}>
                      {ch.username || ch.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel>{t('common.websiteSources')}</SelectLabel>
                  {websiteSources.map((ws: any) => (
                    <SelectItem key={`website-${ws.id}`} value={`website-${ws.id}`}>
                      {ws.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-full sm:w-40 h-9 text-sm">
                <SelectValue placeholder={t('messages.allStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('messages.allStatus')}</SelectItem>
                <SelectItem value="analyzed">{t('messages.analyzed')}</SelectItem>
                <SelectItem value="pending">{t('messages.pending')}</SelectItem>
                <SelectItem value="skipped">{t('messages.skipped')}</SelectItem>
                <SelectItem value="failed">{t('messages.failed')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {messages.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-3 px-1">
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={selectAllMessages}>
            {t('common.selectAll')}
          </Button>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={clearMessageSelection}>
            {t('common.clearSelection')}
          </Button>
          {selectedMessageIds.size > 0 && (
            <>
              <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
                {t('common.selectedCount', { count: selectedMessageIds.size })}
              </span>
              <Button variant="destructive" size="sm" className="h-7 text-xs"
                onClick={() => setBulkDeleteDialogOpen(true)}>
                {t('common.bulkDelete')}
              </Button>
            </>
          )}
        </div>
      )}

      {/* Messages List + Detail */}
      <TooltipProvider delayDuration={400}>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* Left: Messages list */}
        <div className="md:col-span-2 space-y-2">
          {loading ? (
            <div className="space-y-2">
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
              <Card className="shadow-sm">
                <div className="divide-y">
                  {messages.map((msg) => {
                    const statusInfo = getStatusInfo(msg.analysis_status);
                    const StatusIcon = statusInfo.icon;
                    const sourceInfo = getSourceInfo(msg.source_type);
                    const SourceIcon = sourceInfo.icon;
                    const isSelected = selectedMessage?.id === msg.id;
                    return (
                      <div
                        key={msg.id}
                        className={`cursor-pointer transition-colors p-3 ${
                          isSelected ? 'bg-primary/5' : 'hover:bg-muted/40'
                        }`}
                        onClick={() => setSelectedMessage(msg)}
                      >
                        <div className="flex items-start gap-2.5">
                          <Checkbox
                            checked={selectedMessageIds.has(msg.id)}
                            onCheckedChange={() => toggleMessageSelection(msg.id)}
                            onClick={(e) => e.stopPropagation()}
                            className="mt-2.5 shrink-0"
                          />
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                            isSelected ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                          }`}>
                            <SourceIcon className="w-4 h-4" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                              <span className="font-semibold text-sm truncate">
                                {msg.source_type === 'website' ? msg.website_source?.name : msg.channel?.username || t('common.unknown')}
                              </span>
                              <Badge variant={statusInfo.variant} className="text-[10px] px-1.5 py-0">
                                <StatusIcon className="w-2.5 h-2.5 mr-0.5" />
                                {statusInfo.label}
                              </Badge>
                              {msg.is_manual_skip && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                  <Ban className="w-2.5 h-2.5 mr-0.5" />
                                  {t('messages.manualSkip')}
                                </Badge>
                              )}
                              {msg.has_image && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                                  <ImageIcon className="w-2.5 h-2.5 mr-0.5" />
                                  {t('messages.image')}
                                </Badge>
                              )}
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-muted-foreground mb-1.5">
                              <span className="flex items-center gap-0.5">
                                <Calendar className="w-2.5 h-2.5" />
                                {msg.date ? new Date(msg.date).toLocaleString() : t('common.unknown')}
                              </span>
                              {(msg.sender_username || msg.sender_first_name) && (
                                <span className="flex items-center gap-0.5">
                                  <User className="w-2.5 h-2.5" />
                                  {msg.sender_username || msg.sender_first_name}
                                </span>
                              )}
                            </div>
                            <div
                              className="text-xs text-muted-foreground line-clamp-2 leading-relaxed"
                              dangerouslySetInnerHTML={{ __html: msg.text || t('messages.noTextContent') }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Pagination */}
              <div className="flex justify-between items-center pt-1">
                <Button onClick={handlePrevious} disabled={offset === 0} variant="outline" size="sm" className="h-7 text-xs">
                  {t('common.previous')}
                </Button>
                <span className="text-xs text-muted-foreground">
                  {offset + 1}–{Math.min(offset + limit, total)} / {total}
                </span>
                <Button onClick={handleNext} disabled={offset + limit >= total} variant="outline" size="sm" className="h-7 text-xs">
                  {t('common.next')}
                </Button>
              </div>
            </>
          ) : (
            <Card className="shadow-sm">
              <CardContent className="py-20 text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-muted flex items-center justify-center">
                  <MessageSquare className="w-8 h-8 text-muted-foreground opacity-50" />
                </div>
                <p className="font-semibold mb-1">{t('messages.noMessages')}</p>
                <p className="text-sm text-muted-foreground mb-5">{t('messages.fetchHint')}</p>
                <Button asChild variant="outline" size="sm">
                  <a href="/channels">{t('messages.goToChannels')}</a>
                </Button>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Message detail */}
        <div className="md:col-span-3">
          {selectedMessage ? (
            <Card className="h-full flex flex-col shadow-sm">
              <CardHeader className="pb-3">
                <div className="flex items-start gap-3 sm:gap-4">
                  <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-lg sm:text-xl font-bold text-primary-foreground shrink-0">
                    {selectedMessage.source_type === 'website' ? <Globe className="w-6 h-6" /> : <MessageSquare className="w-6 h-6" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg sm:text-xl font-bold leading-tight">
                      {selectedMessage.source_type === 'website'
                        ? (selectedMessage.website_source?.name || t('common.website'))
                        : (selectedMessage.channel?.username || t('common.unknown'))}
                    </CardTitle>
                    <div className="flex items-center gap-2 flex-wrap mt-2">
                      {(() => {
                        const statusInfo = getStatusInfo(selectedMessage.analysis_status);
                        const StatusIcon = statusInfo.icon;
                        return (
                          <Badge variant={statusInfo.variant} className="text-xs">
                            <StatusIcon className="w-3 h-3 mr-1" />
                            {statusInfo.label}
                          </Badge>
                        );
                      })()}
                      {selectedMessage.is_manual_skip && (
                        <Badge variant="outline" className="text-xs">
                          <Ban className="w-3 h-3 mr-1" />
                          {t('messages.manualSkip')}
                        </Badge>
                      )}
                      {selectedMessage.has_image && (
                        <Badge variant="outline" className="text-xs">
                          <ImageIcon className="w-3 h-3 mr-1" />
                          {t('messages.image')}
                        </Badge>
                      )}
                      {selectedMessage.job && (
                        <Button variant="outline" size="sm" asChild className="text-xs h-7 px-2">
                          <a href={`/jobs?jobId=${selectedMessage.job.id}`}>
                            <Briefcase className="w-3 h-3 mr-1" />
                            {t('messages.viewJob')}
                          </a>
                        </Button>
                      )}
                      {selectedMessage.developer && (
                        <Button variant="outline" size="sm" asChild className="text-xs h-7 px-2">
                          <a href={`/developers?developerId=${selectedMessage.developer.id}`}>
                            <Code2 className="w-3 h-3 mr-1" />
                            {t('messages.viewDeveloper')}
                          </a>
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="flex-1 flex flex-col min-h-0">
                {/* Metadata */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-muted-foreground mb-4">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-primary" />
                    <span>{selectedMessage.date ? new Date(selectedMessage.date).toLocaleString() : t('common.unknown')}</span>
                  </div>
                  {(selectedMessage.sender_username || selectedMessage.sender_first_name) && (
                    <div className="flex items-center gap-2">
                      <User className="w-4 h-4 text-primary" />
                      <span>{selectedMessage.sender_username || selectedMessage.sender_first_name}</span>
                    </div>
                  )}
                  {selectedMessage.source_type === 'website' && selectedMessage.website_source?.url && (
                    <div className="flex items-center gap-2 sm:col-span-2">
                      <ExternalLink className="w-4 h-4 text-primary" />
                      <a href={selectedMessage.website_source.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                        {selectedMessage.website_source.url}
                      </a>
                    </div>
                  )}
                  {selectedMessage.skip_reason && (
                    <div className="flex items-center gap-2 sm:col-span-2">
                      <SkipForward className="w-4 h-4 text-primary" />
                      <span>{t('messages.skipReason')}: {selectedMessage.skip_reason}</span>
                    </div>
                  )}
                </div>

                <Separator className="mb-4" />

                {/* Actions */}
                <div className="flex flex-wrap gap-2 mb-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleToggleSkip(selectedMessage.id)}
                    disabled={togglingSkipId === selectedMessage.id}
                  >
                    {togglingSkipId === selectedMessage.id ? (
                      <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                    ) : selectedMessage.is_manual_skip ? (
                      <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                    ) : (
                      <Ban className="w-3.5 h-3.5 mr-1.5" />
                    )}
                    {selectedMessage.is_manual_skip ? t('messages.unskip') : t('messages.skip')}
                  </Button>
                  {(selectedMessage.analysis_status === 'skipped' || selectedMessage.analysis_status === 'failed') && !selectedMessage.is_manual_skip && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => reanalyzeSingle(selectedMessage.id)}
                      disabled={reanalyzingId === selectedMessage.id}
                    >
                      {reanalyzingId === selectedMessage.id ? (
                        <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                      ) : (
                        <RotateCcw className="w-3.5 h-3.5 mr-1.5" />
                      )}
                      {t('messages.reanalyze')}
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      const text = selectedMessage.text?.replace(/<[^>]*>/g, '') || '';
                      const success = await copyToClipboard(text);
                      if (success) {
                        setCopiedId(selectedMessage.id);
                        setTimeout(() => setCopiedId(null), 2000);
                      }
                    }}
                  >
                    {copiedId === selectedMessage.id ? <Check className="w-3.5 h-3.5 mr-1.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 mr-1.5" />}
                    {t('messages.copyText')}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-purple-200 text-purple-700 hover:bg-purple-50"
                    onClick={() => navigate(`/resume?messageId=${selectedMessage.id}&tab=generate`)}
                  >
                    <ScrollText className="w-3.5 h-3.5 mr-1.5" />
                    {t('messages.resumeButton')}
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => { setMessageToDelete(selectedMessage.id); setDeleteDialogOpen(true); }}
                  >
                    <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                    {t('common.delete')}
                  </Button>
                </div>

                {/* Message body */}
                <div className="flex-1 overflow-y-auto rounded-xl border bg-muted/30 p-4">
                  <div
                    className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap break-words prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: selectedMessage.text || t('messages.noTextContent') }}
                  />
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="h-full shadow-sm">
              <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
                <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                  <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-3">
                    <MessageSquare className="w-8 h-8 opacity-40" />
                  </div>
                  <p className="text-sm">{t('messages.selectMessage')}</p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
      </TooltipProvider>

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

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={bulkDeleteDialogOpen} onOpenChange={setBulkDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('messages.bulkDeleteConfirm')}</DialogTitle>
            <DialogDescription>
              {t('messages.bulkDeleteWarning', { count: selectedMessageIds.size })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleBulkDeleteMessages}>
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </>
  );
};

export default Messages;
