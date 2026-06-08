import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Search, Square } from 'lucide-react';
import api from '@/services/api';
import type { Channel, TelegramAccount } from '@/services/api';
import { useWebSocketProgress, useToast } from '@/components/Layout';

const Channels = () => {
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
  const [activeFilter, setActiveFilter] = useState('all');
  const [telegramAccounts, setTelegramAccounts] = useState<TelegramAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
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
      let errorMessage = 'Failed to load Telegram accounts';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getStats();
      setStats(data);
    } catch (e: any) {
      let errorMessage = 'Failed to load stats';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
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
      let errorMessage = 'Failed to load channels';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
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
        showToast('error', 'Error: ' + (data.error || 'Failed to load dialogs'));
      }
    } catch (e: any) {
      // Try to extract error message from response
      let errorMessage = 'Failed to load dialogs';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
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
      showToast('success', 'Channel added successfully!');
      setAddedUsernames(prev => new Set(prev).add(username));
      setTimeout(() => {
        loadChannels();
        // Filter dialogs locally to remove the added channel from the list
        filterDialogsLocally();
      }, 100);
    } catch (e: any) {
      let errorMessage = 'Failed to add channel';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
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
      showToast('success', 'Channel added successfully!');
      setFormData({ username: '', name: '', description: '' });
      setAddedUsernames(prev => new Set(prev).add(formData.username));
      setTimeout(() => {
        loadChannels();
        // Filter dialogs locally to remove the added channel from the list
        filterDialogsLocally();
      }, 100);
    } catch (e: any) {
      let errorMessage = 'Failed to add channel';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
    }
  };

  const fetchAnalyzeChannel = async (channelId: number) => {
    try {
      // Check if Ollama is available before attempting analysis (fetch-analyze includes analysis)
      if (!stats?.ollama_available) {
        showToast('error', 'Ollama is not available. Please check if Ollama is running.');
        return;
      }

      const data = await withLoading(`fetch-analyze-${channelId}`, () => api.fetchAnalyzeChannel(channelId, selectedAccountId || undefined));
      if (data.success) {
        showToast('success', `Fetched ${data.total_new_messages} new messages, found ${data.total_jobs} jobs (${data.days_back_used}d window)`);
        setTimeout(() => loadChannels(), 1500);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown error'));
      }
    } catch (e: any) {
      let errorMessage = 'Failed to fetch and analyze channel';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
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

  const toggleChannel = async (channelId: number) => {
    try {
      await withLoading(`toggle-${channelId}`, () => api.toggleChannel(channelId));
      loadChannels();
    } catch (e: any) {
      let errorMessage = 'Failed to toggle channel';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
    }
  };

  const deleteChannel = async (channelId: number) => {
    try {
      await withLoading(`delete-${channelId}`, () => api.deleteChannel(channelId));
      loadChannels();
      setDeleteDialogOpen(false);
    } catch (e: any) {
      let errorMessage = 'Failed to delete channel';
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', 'Error: ' + errorMessage);
    }
  };

  const confirmDelete = (channelId: number) => {
    setChannelToDelete(channelId);
    setDeleteDialogOpen(true);
  };

  return (
    <>
      <div className="mb-4 flex justify-between items-center">
        <h1 className="text-2xl font-bold">Channels</h1>
        <Button onClick={() => {
          setAddDialogOpen(true);
          filterDialogsLocally();
        }}>
          Add Channel
        </Button>
      </div>

      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Configured Channels ({total})</CardTitle>
          </div>
          <div className="flex gap-2 mt-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <Input
                placeholder="Search channels..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            {(searchQuery || activeFilter !== 'all') && (
              <Button variant="ghost" size="sm" onClick={() => { setSearchQuery(''); setActiveFilter('all'); }}>
                Clear
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {channels.length > 0 ? (
            <>
              {channels.map((channel) => (
                <div key={channel.id} className="p-4 border-b border-gray-200">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="font-semibold flex items-center gap-2">
                        {channel.username}
                        <Badge variant={channel.is_active ? 'default' : 'secondary'}>
                          {channel.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </h3>
                      {channel.name && <p className="font-bold">{channel.name}</p>}
                      {channel.description && <p>{channel.description}</p>}
                      <p className="text-sm text-gray-500">
                        {channel.message_count || 0} messages | {channel.job_count || 0} jobs
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
                    <div className="flex gap-2">
                      {!(loadingActions.has(`fetch-analyze-${channel.id}`) || !!operations[channel.username]) ? (
                        <Button
                          variant="outline"
                          onClick={() => fetchAnalyzeChannel(channel.id)}
                          disabled={loadingActions.has(`fetch-analyze-${channel.id}`)}
                        >
                          Fetch
                        </Button>
                      ) : (
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
                      <Button
                        variant="outline"
                        onClick={() => toggleChannel(channel.id)}
                        disabled={loadingActions.has(`toggle-${channel.id}`) || !!(loadingActions.has(`fetch-analyze-${channel.id}`) || !!operations[channel.username])}
                      >
                        {loadingActions.has(`toggle-${channel.id}`) ? 'Toggling...' : (channel.is_active ? 'Disable' : 'Enable')}
                      </Button>
                      <Button
                        variant="destructive"
                        onClick={() => confirmDelete(channel.id)}
                        disabled={loadingActions.has(`delete-${channel.id}`) || !!(loadingActions.has(`fetch-analyze-${channel.id}`) || !!operations[channel.username])}
                      >
                        {loadingActions.has(`delete-${channel.id}`) ? 'Deleting...' : 'Delete'}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
              {/* Pagination */}
              <div className="flex items-center justify-between pt-3 border-t">
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
            <p>No channels configured yet. Add your first channel above.</p>
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm Delete</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            Are you sure you want to delete this channel? This will also delete all associated messages and jobs.
          </p>
          <div className="flex gap-2 justify-end mt-4">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => channelToDelete && deleteChannel(channelToDelete)}
              disabled={loadingActions.has(`delete-${channelToDelete || 0}`)}
            >
              {loadingActions.has(`delete-${channelToDelete || 0}`) ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Channel Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Channel</DialogTitle>
          </DialogHeader>
          {telegramAccounts.length > 0 && (
            <div className="mb-4">
              <label className="block mb-1 font-medium text-sm">Select Telegram Account</label>
              <select
                value={selectedAccountId || ''}
                onChange={(e) => setSelectedAccountId(e.target.value ? parseInt(e.target.value) : null)}
                className="w-full px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
              >
                <option value="">Select Account</option>
                {telegramAccounts.map(acc => (
                  <option key={acc.id} value={acc.id}>
                    {acc.username ? `@${acc.username}` : acc.phone_number} {acc.is_authenticated ? '✓' : '(not authenticated)'}
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
            {loadingActions.has('load-dialogs') ? 'Loading...' : 'Load from Telegram Account'}
          </Button>
          {showDialogs && (
            <div className="mb-4">
              <h3 className="text-sm font-semibold mb-2">Available Channels & Groups</h3>
              <div className="max-h-[300px] overflow-y-auto border border-gray-200 p-2 mb-2">
                {dialogs.length === 0 ? (
                  <p className="text-sm">No channels or groups found in your Telegram account.</p>
                ) : (
                  dialogs.map((dialog, idx) => (
                      <div key={idx} className="p-2 border-b border-gray-100">
                        <div className="flex justify-between items-center">
                          <div>
                            <p className="font-bold">{dialog.type === 'channel' ? 'Channel' : 'Group'}</p>
                            <p>{dialog.name}</p>
                            <p className="text-sm text-gray-500">{dialog.username || '(no username)'}</p>
                          </div>
                          <Button
                            size="sm"
                            onClick={() => addChannelDirect(dialog.username || '', dialog.name)}
                            disabled={loadingActions.has(`add-${dialog.username}`)}
                          >
                            {loadingActions.has(`add-${dialog.username}`) ? 'Adding...' : 'Add'}
                          </Button>
                        </div>
                      </div>
                    ))
                )}
                {dialogs.filter(dialog => !addedUsernames.has(dialog.username || '')).length === 0 && dialogs.length > 0 && (
                  <p className="text-gray-500 text-sm">All channels have been added.</p>
                )}
              </div>
            </div>
          )}
          <form onSubmit={addChannel}>
            <div className="mb-3">
              <label className="block mb-1 font-medium text-sm">Channel Username *</label>
              <Input
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                placeholder="@channelname or channelname"
                required
              />
            </div>
            <div className="mb-3">
              <label className="block mb-1 font-medium text-sm">Name (optional)</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Display name"
              />
            </div>
            <div className="mb-3">
              <label className="block mb-1 font-medium text-sm">Description (optional)</label>
              <Textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description"
                rows={2}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => setAddDialogOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loadingActions.has('add-channel')}
              >
                {loadingActions.has('add-channel') ? 'Adding...' : 'Add Channel'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default Channels;
