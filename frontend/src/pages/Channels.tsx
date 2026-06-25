import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Search, Square, RefreshCw, Bot } from 'lucide-react';
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [telegramAccounts, setTelegramAccounts] = useState<TelegramAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [listenedChannels, setListenedChannels] = useState<string[]>([]);
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');
  const { progress: wsProgress, channelProgress, operations, stoppingChannels, tokenUsage, messageResults, requestStop } = useWebSocketProgress();

  useEffect(() => {
    if (wsProgress && (wsProgress.type === 'analyze_complete' || wsProgress.type === 'error' || wsProgress.type === 'fetch_complete')) {
      // Reload channels but maintain current pagination
      loadChannels();
    }
  }, [wsProgress]);

  useEffect(() => {
    loadChannels();
    loadStats();
    loadTelegramAccounts();
  }, [offset, searchQuery, activeFilter]);

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
      const params: any = { limit, offset };
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
    <>
      <div className="mb-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <h1 className="text-2xl font-bold">{t('channels.title')}</h1>
        <Button onClick={() => {
          setAddDialogOpen(true);
          filterDialogsLocally();
        }} className="w-full sm:w-auto">
          {t('channels.addChannel')}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>{t('channels.title')} ({total})</CardTitle>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 mt-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder={t('channels.searchPlaceholder')}
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { setSearchParams({}); setSearchQuery(searchInput); } }}
                className="pl-9"
              />
            </div>
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="px-3 py-2 rounded-md border border-gray-200 text-sm bg-white w-full sm:w-auto"
            >
              <option value="all">{t('common.allStatus')}</option>
              <option value="active">{t('channels.active')}</option>
              <option value="inactive">{t('channels.inactive')}</option>
            </select>
            {(searchQuery || activeFilter !== 'all') && (
              <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(''); setSearchInput(''); setActiveFilter('all'); }} className="w-full sm:w-auto">
                {t('common.clear')}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {channels.length > 0 ? (
            <>
              {channels.map((channel) => (
                <div key={channel.id} className="p-4 border-b border-gray-200">
                  <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold flex items-center gap-2 flex-wrap">
                        {channel.username}
                        <Badge variant={channel.is_active ? 'default' : 'secondary'}>
                          {channel.is_active ? t('channels.active') : t('channels.inactive')}
                        </Badge>
                        {(channel.is_listened === 1 || channel.is_listened === true || listenedChannels.includes(channel.username)) && (
                          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                            {t('dashboard.listening')}
                          </Badge>
                        )}
                      </h3>
                      {channel.name && <p className="font-bold">{channel.name}</p>}
                      {channel.description && <p>{channel.description}</p>}
                      <p className="text-sm text-gray-500">
                        {channel.message_count || 0} {t('dashboard.messages')} | {channel.job_count || 0} {t('dashboard.jobs')}
                        {(channel.last_fetch_new_count || 0) > 0 && (
                          <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            +{channel.last_fetch_new_count} {t('channels.fetched')}
                          </span>
                        )}
                        {(channel.pending_count || 0) > 0 && (
                          <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                            {channel.pending_count} {t('channels.pending')}
                          </span>
                        )}
                      </p>
                      {channelProgress[channel.username] && (
                        <div className="mt-2">
                          <div className="flex justify-between text-xs mb-1">
                            <span className={stoppingChannels[channel.username] ? 'text-orange-600 font-medium' : ''}>
                              {stoppingChannels[channel.username] ? t('channels.stopping') : t('channels.analyzing')}
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
                    <div className="flex flex-wrap gap-2 w-full sm:w-auto">
                      <Button
                        size="sm"
                        variant={operations[channel.username]?.type === 'fetch' ? 'destructive' : 'outline'}
                        onClick={() => operations[channel.username]?.type === 'fetch' ? stopAnalyzeChannel(channel.id, channel.username) : fetchChannel(channel.id)}
                        disabled={loadingActions.has(`fetch-${channel.id}`) || operations[channel.username]?.type === 'fetch' && stoppingChannels[channel.id]}
                        className="flex-1 sm:flex-none"
                      >
                        {operations[channel.username]?.type === 'fetch' ? (
                          <>
                            <Square size={12} className="mr-1" />
                            {stoppingChannels[channel.id] ? t('channels.stopping') : t('dashboard.fetching')}
                          </>
                        ) : (
                          <>
                            <RefreshCw size={12} className="mr-1" />
                            {loadingActions.has(`fetch-${channel.id}`) ? t('dashboard.fetching') : t('channels.fetch')}
                          </>
                        )}
                      </Button>
                      <Button
                        size="sm"
                        variant={operations[channel.username]?.type === 'analyze' ? 'destructive' : 'default'}
                        onClick={() => operations[channel.username]?.type === 'analyze' ? stopAnalyzeChannel(channel.id, channel.username) : analyzeChannel(channel.id)}
                        disabled={loadingActions.has(`analyze-${channel.id}`) || operations[channel.username]?.type === 'analyze' && stoppingChannels[channel.id]}
                        className="flex-1 sm:flex-none"
                      >
                        {operations[channel.username]?.type === 'analyze' ? (
                          <>
                            <Square size={12} className="mr-1" />
                            {stoppingChannels[channel.id] ? t('channels.stopping') : t('dashboard.analyzing')}
                          </>
                        ) : (
                          <>
                            <Bot size={12} className="mr-1" />
                            {loadingActions.has(`analyze-${channel.id}`) ? t('dashboard.analyzing') : t('channels.analyze')}
                          </>
                        )}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => toggleChannel(channel.id)}
                        disabled={loadingActions.has(`toggle-${channel.id}`) || !!(loadingActions.has(`fetch-${channel.id}`) || loadingActions.has(`analyze-${channel.id}`) || !!operations[channel.username])}
                        className="flex-1 sm:flex-none"
                      >
                        {loadingActions.has(`toggle-${channel.id}`) ? t('channels.toggling') : (channel.is_active ? t('channels.disable') : t('channels.enable'))}
                      </Button>
                      {/* Listen Toggle - always shown */}
                      <Button
                        variant={listenedChannels.includes(channel.username) ? 'destructive' : 'default'}
                        onClick={() => toggleChannelListener(channel)}
                        disabled={loadingActions.has(`listener-${channel.id}`)}
                        className="flex-1 sm:flex-none"
                      >
                        {loadingActions.has(`listener-${channel.id}`)
                          ? 'Loading...'
                          : listenedChannels.includes(channel.username)
                            ? 'Stop Listening'
                            : 'Listen'
                        }
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => confirmDelete(channel.id)}
                        disabled={loadingActions.has(`delete-${channel.id}`) || !!(loadingActions.has(`fetch-${channel.id}`) || loadingActions.has(`analyze-${channel.id}`) || !!operations[channel.username])}
                        className="flex-1 sm:flex-none"
                      >
                        {loadingActions.has(`delete-${channel.id}`) ? t('channels.deleting') : t('channels.delete')}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              {/* Pagination */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrevious}
                  disabled={offset === 0}
                  className="w-full sm:w-auto"
                >
                  {t('common.previous')}
                </Button>
                <span className="text-sm text-muted-foreground text-center">
                  {t('common.page')} {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNext}
                  disabled={offset + limit >= total}
                  className="w-full sm:w-auto"
                >
                  {t('common.next')}
                </Button>
              </div>
            </>
          ) : (
            <p>{t('channels.noChannels')}</p>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('channels.deleteConfirm')}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
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
              <select
                value={selectedAccountId || ''}
                onChange={(e) => setSelectedAccountId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
              >
                <option value="">{t('telegramAccounts.selectAccount')}</option>
                {telegramAccounts.map(acc => (
                  <option key={acc.id} value={acc.id}>
                    {acc.username ? `@${acc.username}` : acc.phone_number} {acc.is_authenticated ? '✓' : `(${t('telegramAccounts.notAuthenticated')})`}
                  </option>
                ))}
              </select>
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
              <div className="max-h-[300px] overflow-y-auto border border-gray-200 p-2 mb-2">
                {dialogs.length === 0 ? (
                  <p className="text-sm">{t('channels.noDialogsFound')}</p>
                ) : (
                  dialogs.map((dialog, idx) => (
                      <div key={idx} className="p-2 border-b border-gray-100">
                        <div className="flex justify-between items-center">
                          <div>
                            <p className="font-bold">{dialog.type === 'channel' ? t('channels.typeChannel') : t('channels.typeGroup')}</p>
                            <p>{dialog.name}</p>
                            <p className="text-sm text-gray-500">{dialog.username || t('channels.noUsername')}</p>
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
                  <p className="text-gray-500 text-sm">{t('channels.allChannelsAdded')}</p>
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
    </>
  );
};

export default Channels;
