import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Globe, Plus, RefreshCw, Bot, Trash2, Loader2, Edit, Square } from 'lucide-react';
import api from '@/services/api';
import type { WebsiteSource } from '@/services/api';
import { useToast, useWebSocketProgress } from '@/components/Layout';

const Websites = () => {
  const [websiteSources, setWebsiteSources] = useState<WebsiteSource[]>([]);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const { channelProgress, operations } = useWebSocketProgress();
  const [addWebsiteDialogOpen, setAddWebsiteDialogOpen] = useState(false);
  const [newWebsiteName, setNewWebsiteName] = useState('');
  const [newWebsiteUrl, setNewWebsiteUrl] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [websiteToDelete, setWebsiteToDelete] = useState<number | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<WebsiteSource | null>(null);
  const [editPrompt, setEditPrompt] = useState('');
  const [initialLoading, setInitialLoading] = useState(true);

  useEffect(() => {
    loadWebsiteSources();
  }, []);

  const loadWebsiteSources = async () => {
    try {
      const data = await api.getWebsiteSources();
      setWebsiteSources(data.sources || []);
      setInitialLoading(false);
    } catch (e: any) {
      setInitialLoading(false);
      showToast('error', 'Error: ' + (e.message || 'Failed to load website sources'));
    }
  };

  const addWebsiteSource = async () => {
    try {
      const formData = new FormData();
      formData.append('name', newWebsiteName);
      formData.append('url', newWebsiteUrl);
      const data = await api.addWebsiteSource(formData);
      if (data.success) {
        showToast('success', 'Website source added');
        setAddWebsiteDialogOpen(false);
        setNewWebsiteName('');
        setNewWebsiteUrl('');
        loadWebsiteSources();
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const deleteWebsiteSource = async (id: number) => {
    try {
      const data = await api.deleteWebsiteSource(id);
      if (data.success) {
        showToast('success', 'Website source deleted');
        loadWebsiteSources();
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const fetchWebsiteSource = async (id: number) => {
    try {
      setLoadingActions(prev => new Set(prev).add(`fetch-${id}`));
      const data = await api.fetchWebsiteSource(id);
      if (data.success) {
        showToast('success', `Fetched ${data.new_messages} new messages (${data.fetch_method})`);
        loadWebsiteSources();
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    } finally {
      setLoadingActions(prev => {
        const newSet = new Set(prev);
        newSet.delete(`fetch-${id}`);
        return newSet;
      });
    }
  };

  const fetchAllWebsiteSources = async () => {
    try {
      setLoadingActions(prev => new Set(prev).add('fetch-all'));
      const data = await api.fetchAllWebsiteSources();
      if (data.success) {
        const methods = data.fetch_methods?.join(', ') || 'mixed';
        showToast('success', `Fetched ${data.new_messages} new messages from ${data.sources_fetched} source(s) (${methods})`);
        loadWebsiteSources();
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    } finally {
      setLoadingActions(prev => {
        const newSet = new Set(prev);
        newSet.delete('fetch-all');
        return newSet;
      });
    }
  };

  const analyzeWebsiteSource = async (id: number) => {
    try {
      const data = await api.analyzeWebsiteSource(id);
      if (data.success) {
        showToast('success', 'Analysis started');
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const analyzeAllWebsiteSources = async () => {
    try {
      const data = await api.analyzeAllWebsiteSources();
      if (data.success) {
        showToast('success', `Analysis started for ${data.sources} website source(s)`);
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const handleDeleteClick = (id: number) => {
    setWebsiteToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = () => {
    if (websiteToDelete) {
      deleteWebsiteSource(websiteToDelete);
      setDeleteDialogOpen(false);
      setWebsiteToDelete(null);
    }
  };

  const handleEditPrompt = (source: WebsiteSource) => {
    setEditingSource(source);
    setEditPrompt(source.extraction_prompt || '');
    setEditDialogOpen(true);
  };

  const savePrompt = async () => {
    if (!editingSource) return;
    try {
      const formData = new FormData();
      formData.append('extraction_prompt', editPrompt);
      const data = await api.updateWebsiteSource(editingSource.id, formData);
      if (data.success) {
        showToast('success', 'Extraction prompt updated');
        setEditDialogOpen(false);
        loadWebsiteSources();
      } else {
        showToast('error', 'Error: ' + (data.error || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  const stopWebsiteOperation = async (sourceId: number, sourceName: string) => {
    try {
      const data = await api.stopWebsiteSource(sourceId);
      if (data.success) {
        showToast('success', `Stop signal sent for ${sourceName}`);
      } else {
        showToast('error', 'Error: ' + (data.message || 'Unknown'));
      }
    } catch (e: any) {
      showToast('error', 'Error: ' + e.message);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Website Sources</h1>
        <Button onClick={() => setAddWebsiteDialogOpen(true)}>
          <Plus size={16} className="mr-2" />
          Add Website Source
        </Button>
      </div>

      {/* Bulk Actions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Bulk Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={fetchAllWebsiteSources}
              disabled={loadingActions.has('fetch-all')}
            >
              {loadingActions.has('fetch-all') ? <Loader2 size={14} className="mr-2 animate-spin" /> : <RefreshCw size={14} className="mr-2" />}
              Fetch All
            </Button>
            <Button
              onClick={analyzeAllWebsiteSources}
            >
              <Bot size={14} className="mr-2" />
              Analyze All
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Active Operations Progress */}
      {Object.keys(operations).length > 0 && (
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader>
            <CardTitle className="text-sm">Active Operations</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.entries(operations).map(([name, op]) => {
              const progress = channelProgress[name];
              return (
                <div key={name} className="mb-3 last:mb-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-blue-900">{name}</span>
                    <span className="text-xs text-blue-700">{op.type}</span>
                  </div>
                  {progress && (
                    <div className="mt-2">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-blue-700">Processing...</span>
                        <span className="text-blue-700">{(progress as any).analyzed || (progress as any).processed || 0} / {progress.total || 0}</span>
                      </div>
                      <div className="w-full bg-blue-200 rounded-full h-2">
                        <div
                          className="bg-blue-600 h-2 rounded-full transition-all"
                          style={{ width: `${(((progress as any).analyzed || (progress as any).processed || 0) / (progress.total || 1)) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      {/* Website Sources List */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">All Website Sources ({websiteSources.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {initialLoading ? (
            <div className="py-8 text-center">
              <Loader2 className="w-5 h-5 text-gray-400 animate-spin mx-auto mb-2" />
              <p className="text-sm text-gray-500">Loading website sources...</p>
            </div>
          ) : websiteSources.length > 0 ? (
            <div className="space-y-2">
              {websiteSources.map((source) => (
                <div key={source.id} className="p-4 border rounded-lg hover:bg-gray-50 transition-colors">
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold text-gray-900">{source.name}</h3>
                        <Badge variant={source.is_active ? 'default' : 'secondary'} className="text-xs">
                          {source.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                        <Badge variant="outline" className="text-xs">
                          RSS
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{source.url}</p>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        {(source.last_fetch_new_count || 0) > 0 && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            +{source.last_fetch_new_count} fetched
                          </span>
                        )}
                        {source.last_fetch_at && (
                          <span>Last: {new Date(source.last_fetch_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleEditPrompt(source)}
                      >
                        <Edit size={12} className="mr-1" />
                        Prompt
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => fetchWebsiteSource(source.id)}
                        disabled={loadingActions.has(`fetch-${source.id}`) || !!operations[source.name]}
                      >
                        {loadingActions.has(`fetch-${source.id}`) ? <Loader2 size={12} className="mr-1 animate-spin" /> : <RefreshCw size={12} className="mr-1" />}
                        Fetch
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => analyzeWebsiteSource(source.id)}
                        disabled={!!operations[source.name]}
                      >
                        <Bot size={12} className="mr-1" />
                        Analyze
                      </Button>
                      {operations[source.name] && (
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => stopWebsiteOperation(source.id, source.name)}
                        >
                          <Square size={12} className="mr-1" />
                          Stop
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDeleteClick(source.id)}
                      >
                        <Trash2 size={12} />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-12 text-center">
              <Globe size={48} className="text-gray-200 mx-auto mb-4" />
              <p className="text-sm text-gray-500 mb-4">No website sources configured</p>
              <Button variant="outline" onClick={() => setAddWebsiteDialogOpen(true)}>
                <Plus size={14} className="mr-2" />
                Add your first website source
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Website Source Dialog */}
      <Dialog open={addWebsiteDialogOpen} onOpenChange={setAddWebsiteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Website Source</DialogTitle>
            <DialogDescription>
              Add a new website source to crawl for job postings.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <Input
                value={newWebsiteName}
                onChange={(e) => setNewWebsiteName(e.target.value)}
                placeholder="e.g., V2EX"
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">RSS Feed URL</label>
              <Input
                value={newWebsiteUrl}
                onChange={(e) => setNewWebsiteUrl(e.target.value)}
                placeholder="e.g., https://example.com/feed.xml"
                className="mt-1"
              />
            </div>
            <p className="text-xs text-gray-500">
              Enter the full RSS feed URL (e.g., /feed.xml, /rss, /atom.xml)
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddWebsiteDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={addWebsiteSource}>
              Add Source
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Website Source</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this website source? This will also delete all associated messages, jobs, and developers.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Extraction Prompt Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Extraction Prompt</DialogTitle>
            <DialogDescription>
              Customize the Ollama prompt for extracting job data from {editingSource?.name}. Leave empty to use the default prompt for this site type.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">Custom Prompt</label>
              <Textarea
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                placeholder="Enter custom extraction prompt..."
                className="mt-1 min-h-[200px] font-mono text-sm"
              />
            </div>
            <p className="text-xs text-gray-500">
              The prompt should instruct Ollama to extract job postings in JSON format. See the default prompts in web_crawler/prompts.py for reference.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={savePrompt}>
              Save Prompt
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Websites;
