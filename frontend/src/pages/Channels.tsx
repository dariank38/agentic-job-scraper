import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Search, Square, RefreshCw, Bot, Radio, Plus, Zap, MessageSquare, Briefcase } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import api from '@/services/api';
import type { Channel, TelegramAccount } from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

const Channels = () => {
  const { t } = useTranslation();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [dialogs, setDialogs] = useState<any[]>([]);
  const [allDialogs, setAllDialogs] = useState<any[]>([]);
  const [showDialogs, setShowDialogs] = useState(false);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const [formData, setFormData] = useState({ username: '', name: '', description: '' });
  const [addedUsernames, setAddedUsernames] = useState<Set<string>>(new Set());
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [channelToDelete, setChannelToDelete] = useState<number | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [total, setTotal] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [telegramAccounts, setTelegramAccounts] = useState<TelegramAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [listenedChannels, setListenedChannels] = useState<string[]>([]);
  const limit = 100;
  const { progress: wsProgress, channelProgress, operations, stoppingChannels, tokenUsage, messageResults, requestStop } = useWebSocketProgress();

  useEffect(() => {
    if (wsProgress && (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error' || wsProgress.type === 'fetch_complete')) {
      // Reload channels
      loadChannels();
    }
  }, [wsProgress]);

  useEffect(() => {
    loadChannels();
    loadStats();
    loadTelegramAccounts();
  }, [searchQuery, activeFilter]);

  useEffect(() => {
    if (telegramAccounts.length > 0) {
      checkListenerStatus();
    }
  }, [telegramAccounts]);

  const checkListenerStatus = async () => {
    try {
      // Get all authenticated accounts first
      const accounts = telegramAccounts.length > 0 ? telegramAccounts : await api.getTelegramAccounts();
      const authenticatedAccounts = accounts.filter((a: TelegramAccount) => a.is_authenticated);

      // Check all accounts and merge listened channels
      const allListenedChannels: string[] = [];

      for (const account of authenticatedAccounts) {
        try {
          const statusData = await api.getListenerStatus(account.id);
          if (statusData.running) {
            const channelsData = await api.getListenerChannels(account.id);
            if (channelsData.listening_to) {
              // Normalize usernames to include @ prefix for comparison with database
              const normalizedChannels = channelsData.listening_to.map((username: string) =>
                username.startsWith('@') ? username : `@${username}`
              );
              allListenedChannels.push(...normalizedChannels);
            }
          }
        } catch (e) {
          // Skip accounts that fail
        }
      }

      setListenedChannels([...new Set(allListenedChannels)]);
    } catch (e: any) {
      // Silently ignore errors
    }
  };

  const loadTelegramAccounts = async () => {
    try {
      const accounts = await api.getTelegramAccounts();
      setTelegramAccounts(accounts);
      // Auto-select first active authenticated account
      const activeAccount = accounts.find(acc => acc.is_active && acc.is_authenticated);
      if (activeAccount) {
        setSelectedAccountId(activeAccount.id);
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToLoad')} ${t('telegramAccounts.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (e: any) {
      let errorMessage = `${t('common.failedToLoad')} stats`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const loadChannels = async () => {
    try {
      const params: any = { limit };
      if (searchQuery) params.search = searchQuery;
      if (activeFilter === 'active') params.is_active = true;
      if (activeFilter === 'inactive') params.is_active = false;
      const data = await api.getChannels(params);
      setChannels(data.channels);
      setTotal(data.total || 0);
    } catch (e: any) {
      let errorMessage = `${t('common.failedToLoad')} ${t('channels.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
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

  const loadTelegramDialogs = async () => {
    try {
      const data = await withLoading('load-dialogs', () => api.getTelegramDialogs(selectedAccountId || undefined));
      if (data.success) {
        setAllDialogs(data.dialogs);
        setShowDialogs(true);
        filterDialogsLocally(data.dialogs);
      } else {
        showToast('error', `${t('common.error')}: ${data.error || t('common.failedToLoad')} dialogs`);
      }
    } catch (e: any) {
      // Try to extract error message from response
      let errorMessage = `${t('common.failedToLoad')} dialogs`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const filterDialogsLocally = (dialogsList = allDialogs) => {
    // Backend now handles primary filtering, this is just a safety layer
    // Also filter out channels added during this session
    const filteredDialogs = dialogsList.filter(
      (dialog: any) => {
        const username = (dialog.username || '').toLowerCase();
        return !addedUsernames.has(username);
      }
    );
    setDialogs(filteredDialogs);
  };

  const addChannelDirect = async (username: string, name: string) => {
    const data = new FormData();
    data.append('username', username);
    data.append('name', name);
    data.append('description', '');
    if (selectedAccountId) {
      data.append('telegram_account_id', selectedAccountId.toString());
    }

    try {
      await withLoading(`add-${username}`, () => api.addChannel(data));
      showToast('success', t('channels.addedSuccessfully'));
      setAddedUsernames(prev => new Set(prev).add(username));
      loadChannels();
      filterDialogsLocally();
    } catch (e: any) {
      let errorMessage = `${t('common.failedToAdd')} ${t('channels.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const addChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    const data = new FormData();
    data.append('username', formData.username);
    data.append('name', formData.name);
    data.append('description', formData.description);
    if (selectedAccountId) {
      data.append('telegram_account_id', selectedAccountId.toString());
    }

    try {
      await withLoading('add-channel', () => api.addChannel(data));
      showToast('success', t('channels.addedSuccessfully'));
      setFormData({ username: '', name: '', description: '' });
      setAddedUsernames(prev => new Set(prev).add(formData.username));
      loadChannels();
      filterDialogsLocally();
    } catch (e: any) {
      let errorMessage = `${t('common.failedToAdd')} ${t('channels.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const fetchChannel = async (channelId: number) => {
    try {
      const data = await withLoading(`fetch-${channelId}`, () => api.fetchChannel(channelId, selectedAccountId || undefined));
      if (data.success) {
        showToast('success', data.message || t('dashboard.fetchStarted'));
        // Data will be updated via WebSocket
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const analyzeChannel = async (channelId: number) => {
    try {
      if (!stats?.ollama_available) {
        showToast('error', t('channels.ollamaUnavailable'));
        return;
      }

      const data = await withLoading(`analyze-${channelId}`, () => api.analyzeChannel(channelId));
      if (data.success) {
        showToast('success', data.message || t('dashboard.analysisStartedSingle'));
        // Data will be updated via WebSocket
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
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
        showToast('success', t('channels.stopSignalSent'));
      } else {
        showToast('warning', data.message || t('channels.noActiveAnalysis'));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const toggleChannel = async (channelId: number) => {
    try {
      await withLoading(`toggle-${channelId}`, () => api.toggleChannel(channelId));
      loadChannels();
    } catch (e: any) {
      let errorMessage = `${t('common.failedToToggle')} ${t('channels.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const deleteChannel = async (channelId: number) => {
    try {
      await withLoading(`delete-${channelId}`, () => api.deleteChannel(channelId));
      loadChannels();
      setDeleteDialogOpen(false);
    } catch (e: any) {
      let errorMessage = `${t('common.failedToDelete')} ${t('channels.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', `${t('common.error')}: ${errorMessage}`);
    }
  };

  const confirmDelete = (channelId: number) => {
    setChannelToDelete(channelId);
    setDeleteDialogOpen(true);
  };

  const toggleChannelListener = async (channel: Channel) => {
    const actionKey = `listener-${channel.id}`;
    try {
      setLoadingActions(prev => new Set(prev).add(actionKey));

      // Use database state first, fallback to runtime state
      const isListening = channel.is_listened || listenedChannels.includes(channel.username);

      if (isListening) {
        // Stop listening to this channel
        const data = await api.removeListenerChannels([channel.username], channel.telegram_account_id || undefined);
        if (data.success) {
          showToast('success', t('channels.channelRemovedFromListener'));
          // Reload channels to get updated is_listened state from database
          await loadChannels();
          // Refresh all listened channels to ensure UI sync
          await checkListenerStatus();
        } else {
          showToast('error', data.error || t('channels.failedToRemoveChannelFromListener'));
        }
      } else {
        // Determine which account to use
        let accountId = channel.telegram_account_id;
        if (!accountId) {
          // Use selected account or auto-select if only one
          const authenticatedAccounts = telegramAccounts.filter(a => a.is_authenticated);
          if (selectedAccountId) {
            accountId = selectedAccountId;
          } else if (authenticatedAccounts.length === 1) {
            accountId = authenticatedAccounts[0].id;
          } else if (authenticatedAccounts.length === 0) {
            showToast('error', t('channels.noAuthenticatedAccount'));
            return;
          } else {
            showToast('error', t('channels.selectAccountFirst'));
            return;
          }
        }

        // Check if listener is running for this account
        const statusData = await api.getListenerStatus(accountId);

        if (!statusData.running) {
          // Start listener with just this channel
          const startData = await api.startListener([channel.username], false, accountId);
          if (startData.success) {
            showToast('success', t('channels.listenerStartedFor', { channel: channel.username }));
            // Reload channels to get updated is_listened state from database
            await loadChannels();
            // Refresh all listened channels to ensure UI sync
            await checkListenerStatus();
          } else {
            showToast('error', startData.error || t('channels.failedToStartListener'));
          }
        } else {
          // Add channel to existing listener
          const data = await api.addListenerChannels([channel.username], accountId);
          if (data.success) {
            showToast('success', t('channels.channelAddedToListener'));
            // Reload channels to get updated is_listened state from database
            await loadChannels();
            // Refresh all listened channels to ensure UI sync
            await checkListenerStatus();
          } else {
            showToast('error', data.error || t('channels.failedToAddChannelToListener'));
          }
        }
      }
    } catch (e: any) {
      showToast('error', `${t('channels.failedToToggleListener')}: ${e.message}`);
    } finally {
      setLoadingActions(prev => {
        const next = new Set(prev);
        next.delete(actionKey);
        return next;
      });
    }
  };

  return (
    <TooltipProvider delayDuration={400}>
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl mb-5 bg-gradient-to-br from-blue-600 via-cyan-600 to-teal-600 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Radio className="w-5 h-5" />
              <h1 className="text-xl font-bold tracking-tight">{t('channels.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{total} {t('channels.title').toLowerCase()} · {channels.filter(c => c.is_active).length} {t('channels.active').toLowerCase()}</p>
          </div>
          <Button
            onClick={() => { setAddDialogOpen(true); filterDialogsLocally(); }}
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm w-full sm:w-auto"
          >
            <Plus className="w-4 h-4 mr-1.5" />
            {t('channels.addChannel')}
          </Button>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder={t('channels.searchPlaceholder')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { setSearchQuery(searchInput); } }}
                className="pl-9"
              />
            </div>
            <Select value={activeFilter} onValueChange={setActiveFilter}>
              <SelectTrigger className="w-full sm:w-36 h-9 text-sm">
                <SelectValue placeholder={t('common.allStatus')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('common.allStatus')}</SelectItem>
                <SelectItem value="active">{t('channels.active')}</SelectItem>
                <SelectItem value="inactive">{t('channels.inactive')}</SelectItem>
              </SelectContent>
            </Select>
            {(searchQuery || activeFilter !== 'all') && (
              <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(''); setSearchInput(''); setActiveFilter('all'); }}>
                {t('common.clear')}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {channels.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
              {channels.map((channel) => {
                const prog = channelProgress[channel.username];
                const isFetching = operations[channel.username]?.type === 'fetch';
                const isAnalyzing = operations[channel.username]?.type === 'analyze';
                const isStopping = stoppingChannels[channel.username];
                const isListened = channel.is_listened === 1 || channel.is_listened === true || listenedChannels.includes(channel.username);
                const pct = prog ? Math.round((prog.analyzed / Math.max(prog.total, 1)) * 100) : 0;
                const results = messageResults[channel.username] || [];
                const hasPending = (channel.pending_count || 0) > 0;
                return (
                  <Card key={channel.id} className={`hover:shadow-md transition-shadow ${hasPending ? 'border-amber-300 bg-amber-50/50' : ''}`}>
                    <CardContent className="p-4">
                      <div className="flex flex-col gap-3">
                        {/* Header: avatar + info */}
                        <div className="flex gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 font-bold text-sm ${
                            channel.is_active ? 'bg-blue-100 text-blue-700' : 'bg-muted text-muted-foreground'
                          }`}>
                            {(channel.username || '@').substring(0, 2).toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <span className="font-semibold text-sm truncate">{channel.username}</span>
                              <Badge variant={channel.is_active ? 'default' : 'secondary'} className="text-xs px-1.5 py-0 shrink-0">
                                {channel.is_active ? t('channels.active') : t('channels.inactive')}
                              </Badge>
                              {isListened && (
                                <Badge className="bg-green-50 text-green-700 border border-green-200 text-xs px-1.5 py-0 shrink-0">
                                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 mr-1 inline-block animate-pulse" />
                                  {t('dashboard.listening')}
                                </Badge>
                              )}
                            </div>
                            {channel.name && <p className="text-xs font-medium text-muted-foreground truncate">{channel.name}</p>}
                          </div>
                        </div>
                        
                        {/* Stats */}
                        <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                          <span className="flex items-center gap-1">
                            <MessageSquare className="w-3 h-3" />
                            {channel.message_count || 0}
                          </span>
                          <span className="flex items-center gap-1">
                            <Briefcase className="w-3 h-3" />
                            {channel.job_count || 0}
                          </span>
                          {(channel.last_fetch_new_count || 0) > 0 && (
                            <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] px-1.5 py-0">+{channel.last_fetch_new_count} {t('channels.fetched')}</Badge>
                          )}
                          {(channel.pending_count || 0) > 0 && (
                            <Badge className="bg-amber-50 text-amber-700 border-amber-200 text-[10px] px-1.5 py-0">{channel.pending_count} {t('channels.pending')}</Badge>
                          )}
                        </div>
                        
                        {/* Progress */}
                        {prog && (
                          <div className="space-y-1">
                            <div className="flex justify-between text-[10px] text-muted-foreground">
                              <span className={isStopping ? 'text-orange-600 font-medium' : 'text-blue-600 font-medium'}>
                                {isStopping ? t('channels.stopping') : t('channels.analyzing')} — {pct}%
                              </span>
                              <span>{prog.analyzed}/{prog.total}</span>
                            </div>
                            <Progress value={pct} className={`h-1.5 ${isStopping ? '[&>div]:bg-orange-500' : ''}`} />
                            {tokenUsage[channel.username] && (
                              <div className="flex gap-2 text-[10px] text-muted-foreground">
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                                  <Zap className="w-2.5 h-2.5 mr-0.5" />
                                  {(tokenUsage[channel.username].total / 1000).toFixed(1)}k tok
                                </Badge>
                              </div>
                            )}
                            {results.length > 0 && (
                              <div className="flex gap-2 text-[10px]">
                                <span className="text-emerald-600">✓ {results.filter((r: any) => r.status === 'success').length}</span>
                                <span className="text-amber-500">⚠ {results.filter((r: any) => r.status === 'json_cutoff').length}</span>
                                <span className="text-red-500">✗ {results.filter((r: any) => r.status === 'failed').length}</span>
                              </div>
                            )}
                          </div>
                        )}
                        
                        {/* Actions */}
                        <div className="flex flex-wrap gap-1.5 pt-2 border-t">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="sm" className="h-7 text-xs flex-1"
                                variant={isFetching ? 'destructive' : 'outline'}
                                onClick={() => isFetching ? stopAnalyzeChannel(channel.id, channel.username) : fetchChannel(channel.id)}
                                disabled={loadingActions.has(`fetch-${channel.id}`) || (isFetching && isStopping)}
                              >
                                {isFetching ? <><Square size={10} className="mr-1" />{isStopping ? t('channels.stopping') : t('dashboard.fetching')}</> : <><RefreshCw size={10} className="mr-1" />{t('channels.fetch')}</>}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{isFetching ? t('common.stop') : t('channels.fetch')}</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="sm" className="h-7 text-xs flex-1"
                                variant={isAnalyzing ? 'destructive' : 'default'}
                                onClick={() => isAnalyzing ? stopAnalyzeChannel(channel.id, channel.username) : analyzeChannel(channel.id)}
                                disabled={loadingActions.has(`analyze-${channel.id}`) || (isAnalyzing && isStopping)}
                              >
                                {isAnalyzing ? <><Square size={10} className="mr-1" />{isStopping ? t('channels.stopping') : t('dashboard.analyzing')}</> : <><Bot size={10} className="mr-1" />{t('channels.analyze')}</>}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{isAnalyzing ? t('common.stop') : t('channels.analyze')}</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="sm" className="h-7 text-xs" variant="outline"
                                onClick={() => toggleChannel(channel.id)}
                                disabled={loadingActions.has(`toggle-${channel.id}`) || !!(operations[channel.username])}
                              >
                                {loadingActions.has(`toggle-${channel.id}`) ? t('channels.toggling') : channel.is_active ? t('channels.disable') : t('channels.enable')}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{channel.is_active ? t('channels.disable') : t('channels.enable')}</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="sm" className="h-7 text-xs"
                                variant={isListened ? 'destructive' : 'outline'}
                                onClick={() => toggleChannelListener(channel)}
                                disabled={loadingActions.has(`listener-${channel.id}`)}
                              >
                                <Radio size={10} className="mr-1" />
                                {isListened ? t('common.stop') : t('common.listen')}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{isListened ? t('common.stop') : t('common.listen')}</TooltipContent>
                          </Tooltip>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="sm" className="h-7 text-xs" variant="ghost"
                                onClick={() => confirmDelete(channel.id)}
                                disabled={loadingActions.has(`delete-${channel.id}`) || !!(operations[channel.username])}
                              >
                                ✕
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{t('channels.delete')}</TooltipContent>
                          </Tooltip>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-3">
                <Radio className="w-7 h-7 opacity-40" />
              </div>
              <p className="text-sm">{t('channels.noChannels')}</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('channels.deleteConfirm')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-foreground/70">
            {t('channels.deleteWarning')}
          </p>
          <div className="flex gap-2 justify-end mt-4">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={() => channelToDelete && deleteChannel(channelToDelete)}
              disabled={loadingActions.has(`delete-${channelToDelete || 0}`)}
            >
              {loadingActions.has(`delete-${channelToDelete || 0}`) ? t('channels.deleting') : t('channels.delete')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Channel Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('channels.addChannel')}</DialogTitle>
          </DialogHeader>
          {telegramAccounts.length > 0 && (
            <div className="mb-4">
              <label className="block mb-1 font-medium text-sm">{t('telegramAccounts.title')}</label>
              <Select
                value={selectedAccountId?.toString() || ''}
                onValueChange={(val) => setSelectedAccountId(val ? parseInt(val) : null)}
              >
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue placeholder={t('telegramAccounts.selectAccount')} />
                </SelectTrigger>
                <SelectContent>
                  {telegramAccounts.map(acc => (
                    <SelectItem key={acc.id} value={acc.id.toString()}>
                      {acc.username ? `@${acc.username}` : acc.phone_number}{' '}
                      {acc.is_authenticated ? '✓' : `(${t('telegramAccounts.notAuthenticated')})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <Button
            className="mb-4 w-full"
            onClick={loadTelegramDialogs}
            disabled={loadingActions.has('load-dialogs') || !selectedAccountId}
          >
            {loadingActions.has('load-dialogs') ? t('channels.loading') : t('channels.loadFromTelegram')}
          </Button>
          {showDialogs && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold mb-2">{t('channels.availableChannels')}</h3>
              <div className="max-h-[300px] overflow-y-auto border rounded-lg p-2 mb-2">
                {dialogs.length === 0 ? (
                  <p className="text-sm">{t('channels.noDialogsFound')}</p>
                ) : (
                  dialogs.map((dialog, idx) => (
                      <div key={idx} className="p-2 border-b last:border-b-0">
                        <div className="flex justify-between items-center">
                          <div>
                            <p className="font-bold">{dialog.type === 'channel' ? t('channels.typeChannel') : t('channels.typeGroup')}</p>
                            <p>{dialog.name}</p>
                            <p className="text-sm text-muted-foreground">{dialog.username || t('channels.noUsername')}</p>
                          </div>
                          <Button
                            size="sm"
                            onClick={() => addChannelDirect(dialog.username || '', dialog.name)}
                            disabled={loadingActions.has(`add-${dialog.username}`)}
                          >
                            {loadingActions.has(`add-${dialog.username}`) ? t('common.adding') : t('channels.addChannel')}
                          </Button>
                        </div>
                      </div>
                    ))
                )}
                {dialogs.filter(dialog => !addedUsernames.has(dialog.username || '')).length === 0 && dialogs.length > 0 && (
                  <p className="text-sm text-muted-foreground">{t('channels.allChannelsAdded')}</p>
                )}
              </div>
            </div>
          )}
          <form onSubmit={addChannel}>
            <div className="mb-3">
              <label className="block mb-1 font-medium text-sm">{t('channels.channelUsernameLabel')}</label>
              <Input
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder={t('channels.channelUsernamePlaceholder')}
                required
              />
            </div>
            <div className="mb-3">
              <label className="block mb-1 font-medium text-sm">{t('channels.nameOptional')}</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder={t('channels.nameOptionalPlaceholder')}
              />
            </div>
            <div className="mb-3">
              <label className="block mb-1 font-medium text-sm">{t('channels.descriptionOptional')}</label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('channels.descriptionOptionalPlaceholder')}
                rows={2}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddDialogOpen(false)}
              >
                {t('common.cancel')}
              </Button>
              <Button
                type="submit"
                disabled={loadingActions.has('add-channel')}
              >
                {loadingActions.has('add-channel') ? t('common.adding') : t('channels.addChannel')}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  );
};

export default Channels;
