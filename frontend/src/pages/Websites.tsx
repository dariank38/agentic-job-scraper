import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Globe, Plus, RefreshCw, Bot, Trash2, Loader2, Edit, Square, Zap, ExternalLink, Calendar } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import api from '@/services/api';
import type { WebsiteSource } from '@/services/api';
import { useToast, useWebSocketProgress } from '@/components/Layout';

const Websites = () => {
  const { t } = useTranslation();
  const [websiteSources, setWebsiteSources] = useState<WebsiteSource[]>([]);
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const { showToast } = useToast();
  const { channelProgress, operations, tokenUsage, stoppingChannels, requestStop } = useWebSocketProgress();
  const [addWebsiteDialogOpen, setAddWebsiteDialogOpen] = useState(false);
  const [newWebsiteName, setNewWebsiteName] = useState('');
  const [newWebsiteUrl, setNewWebsiteUrl] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [websiteToDelete, setWebsiteToDelete] = useState<number | null>(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingSource, setEditingSource] = useState<WebsiteSource | null>(null);
  const [editPrompt, setEditPrompt] = useState('');
  const [editCookies, setEditCookies] = useState('');
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
      showToast('error', `${t('common.error')}: ${e.message || t('common.failedToLoad')} ${t('websites.title')}`);
    }
  };

  const addWebsiteSource = async () => {
    try {
      const formData = new FormData();
      formData.append('name', newWebsiteName);
      formData.append('url', newWebsiteUrl);
      const data = await api.addWebsiteSource(formData);
      if (data.success) {
        showToast('success', t('websites.sourceAdded'));
        setAddWebsiteDialogOpen(false);
        setNewWebsiteName('');
        setNewWebsiteUrl('');
        loadWebsiteSources();
      } else {
        showToast('error', `${t('common.error')}: ${data.error || t('common.error')}`);
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ${e.message}`);
    }
  };

  const deleteWebsiteSource = async (id: number) => {
    try {
      const data = await api.deleteWebsiteSource(id);
      if (data.success) {
        showToast('success', t('websites.sourceDeleted'));
        loadWebsiteSources();
      } else {
        showToast('error', `${t('common.error')}: ${data.error || t('common.error')}`);
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ${e.message}`);
    }
  };

  const fetchWebsiteSource = async (id: number) => {
    try {
      setLoadingActions(prev => new Set(prev).add(`fetch-${id}`));
      const data = await api.fetchWebsiteSource(id);
      if (data.success) {
        showToast('success', t('websites.fetchedMessages', { count: data.new_messages, method: data.fetch_method }));
        loadWebsiteSources();
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
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
        const methods = data.fetch_methods?.join(', ') || t('common.mixed');
        showToast('success', t('websites.fetchedAllMessages', { count: data.new_messages, sources: data.sources_fetched, methods }));
        loadWebsiteSources();
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
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
      setLoadingActions(prev => new Set(prev).add(`analyze-${id}`));
      const data = await api.analyzeWebsiteSource(id);
      if (data.success) {
        showToast('success', data.message || t('websites.analysisStarted'));
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    } finally {
      setLoadingActions(prev => {
        const newSet = new Set(prev);
        newSet.delete(`analyze-${id}`);
        return newSet;
      });
    }
  };

  const analyzeAllWebsiteSources = async () => {
    try {
      setLoadingActions(prev => new Set(prev).add('analyze-all'));
      const data = await api.analyzeAllWebsiteSources();
      if (data.success) {
        showToast('success', data.message || t('websites.analysisStarted'));
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    } finally {
      setLoadingActions(prev => {
        const newSet = new Set(prev);
        newSet.delete('analyze-all');
        return newSet;
      });
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
    setEditCookies(source.cookies || '');
    setEditDialogOpen(true);
  };

  const savePrompt = async () => {
    if (!editingSource) return;
    try {
      const formData = new FormData();
      formData.append('extraction_prompt', editPrompt);
      if (editCookies) {
        formData.append('cookies', editCookies);
      }
      const data = await api.updateWebsiteSource(editingSource.id, formData);
      if (data.success) {
        showToast('success', t('websites.promptUpdated'));
        setEditDialogOpen(false);
        loadWebsiteSources();
      } else {
        showToast('error', `${t('common.error')}: ` + (data.error || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  const stopWebsiteOperation = async (sourceId: number, sourceName: string) => {
    try {
      requestStop(sourceId, sourceName);
      const data = await api.stopWebsiteSource(sourceId);
      if (data.success) {
        showToast('success', t('websites.stopSignalSent', { name: sourceName }));
      } else {
        showToast('error', `${t('common.error')}: ` + (data.message || t('common.unknown')));
      }
    } catch (e: any) {
      showToast('error', `${t('common.error')}: ` + e.message);
    }
  };

  return (
    <TooltipProvider delayDuration={400}>
    <div className="space-y-5">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-emerald-600 via-teal-600 to-cyan-600 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Globe className="w-5 h-5" />
              <h1 className="text-xl font-bold tracking-tight">{t('websites.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{websiteSources.length} {t('websites.title').toLowerCase()} · {websiteSources.filter(s => s.is_active).length} {t('websites.active').toLowerCase()}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm h-9"
              onClick={fetchAllWebsiteSources} disabled={loadingActions.has('fetch-all')}>
              {loadingActions.has('fetch-all') ? <Loader2 size={14} className="mr-1.5 animate-spin" /> : <RefreshCw size={14} className="mr-1.5" />}
              {t('websites.fetchAll')}
            </Button>
            <Button className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm h-9"
              onClick={analyzeAllWebsiteSources}>
              <Bot size={14} className="mr-1.5" />
              {t('websites.analyzeAll')}
            </Button>
            <Button className="bg-white text-emerald-700 hover:bg-white/90 border-0 h-9"
              onClick={() => setAddWebsiteDialogOpen(true)}>
              <Plus size={14} className="mr-1.5" />
              {t('websites.addWebsite')}
            </Button>
          </div>
        </div>
      </div>

      {/* Active Operations */}
      {Object.keys(operations).length > 0 && (
        <Card className="border-blue-200 bg-gradient-to-r from-blue-50 to-cyan-50">
          <CardContent className="pt-4 pb-4">
            <p className="text-xs font-semibold text-blue-700 uppercase tracking-wider mb-3">{t('websites.activeOperations')}</p>
            <div className="space-y-3">
              {Object.entries(operations).map(([name, op]) => {
                const progress = channelProgress[name];
                const pct = progress ? Math.round(((progress as any).analyzed || 0) / Math.max(progress.total || 1, 1) * 100) : 0;
                return (
                  <div key={name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-blue-900">{name}</span>
                      <Badge className="bg-blue-100 text-blue-700 border-blue-200 text-xs">{op.type} — {pct}%</Badge>
                    </div>
                    {progress && <Progress value={pct} className="h-1.5" />}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Website Sources List */}
      <Card className="shadow-sm">
        <CardContent className="p-0">
          {initialLoading ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
              <Loader2 className="w-6 h-6 animate-spin" />
              <p className="text-sm">{t('common.loading')}</p>
            </div>
          ) : websiteSources.length > 0 ? (
            <div className="divide-y">
              {websiteSources.map((source) => {
                const prog = channelProgress[source.name];
                const isStopping = stoppingChannels[source.id] || stoppingChannels[source.name];
                const isActive = loadingActions.has(`fetch-${source.id}`) || loadingActions.has(`analyze-${source.id}`) || !!prog;
                const pct = prog ? Math.round((prog.analyzed / Math.max(prog.total, 1)) * 100) : 0;
                return (
                  <div key={source.id} className="p-4 hover:bg-muted/30 transition-colors">
                    <div className="flex flex-col sm:flex-row gap-4">
                      <div className="flex gap-3 flex-1 min-w-0">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                          source.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-muted text-muted-foreground'
                        }`}>
                          <Globe size={18} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className="font-semibold text-sm">{source.name}</span>
                            <Badge variant={source.is_active ? 'default' : 'secondary'} className="text-xs px-1.5 py-0">
                              {source.is_active ? t('websites.active') : t('websites.inactive')}
                            </Badge>
                            <Badge variant="outline" className="text-xs px-1.5 py-0">{t('common.rss')}</Badge>
                            {(source.last_fetch_new_count || 0) > 0 && (
                              <Badge className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] px-1.5 py-0">+{source.last_fetch_new_count} {t('websites.fetched')}</Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground truncate mb-1 flex items-center gap-1">
                            <ExternalLink size={10} className="shrink-0" />
                            {source.url}
                          </p>
                          {source.last_fetch_at && (
                            <p className="text-[10px] text-muted-foreground flex items-center gap-1">
                              <Calendar size={9} />
                              {t('websites.last')}: {new Date(source.last_fetch_at).toLocaleDateString()}
                            </p>
                          )}
                          {prog && (
                            <div className="mt-2.5 space-y-1">
                              <div className="flex justify-between text-[10px]">
                                <span className={isStopping ? 'text-orange-600 font-medium' : 'text-emerald-600 font-medium'}>
                                  {isStopping ? t('dashboard.stoppingProgress') : t('dashboard.analyzingProgress')} — {pct}%
                                </span>
                                <span className="text-muted-foreground">{prog.analyzed}/{prog.total}</span>
                              </div>
                              <Progress value={pct} className={`h-1.5 ${isStopping ? '[&>div]:bg-orange-500' : ''}`} />
                              {tokenUsage[source.name] && (
                                <Badge variant="outline" className="text-[10px] px-1.5 py-0 font-mono">
                                  <Zap className="w-2.5 h-2.5 mr-0.5" />
                                  {(tokenUsage[source.name].total / 1000).toFixed(1)}k tok
                                </Badge>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1.5 sm:items-start">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button size="sm" className="h-7 text-xs" variant="outline" onClick={() => handleEditPrompt(source)}>
                              <Edit size={10} className="mr-1" />{t('websites.prompt')}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('websites.customPrompt')}</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button size="sm" className="h-7 text-xs" variant="outline"
                              onClick={() => fetchWebsiteSource(source.id)} disabled={isActive}>
                              {loadingActions.has(`fetch-${source.id}`) ? <Loader2 size={10} className="mr-1 animate-spin" /> : <RefreshCw size={10} className="mr-1" />}
                              {t('websites.fetch')}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('websites.fetch')}</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button size="sm" className="h-7 text-xs"
                              onClick={() => analyzeWebsiteSource(source.id)} disabled={isActive}>
                              <Bot size={10} className="mr-1" />{t('websites.analyze')}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('websites.analyze')}</TooltipContent>
                        </Tooltip>
                        {isActive && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button size="sm" className="h-7 text-xs" variant="destructive"
                                onClick={() => stopWebsiteOperation(source.id, source.name)} disabled={isStopping}>
                                <Square size={10} className="mr-1" />
                                {isStopping ? t('channels.stopping') : t('common.stop')}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{t('common.stop')}</TooltipContent>
                          </Tooltip>
                        )}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button size="sm" className="h-7 text-xs" variant="ghost"
                              onClick={() => handleDeleteClick(source.id)}>
                              <Trash2 size={10} />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('common.delete')}</TooltipContent>
                        </Tooltip>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4">
                <Globe size={28} className="opacity-40" />
              </div>
              <p className="text-sm mb-4">{t('websites.noWebsites')}</p>
              <Button variant="outline" onClick={() => setAddWebsiteDialogOpen(true)}>
                <Plus size={14} className="mr-1.5" />{t('websites.addWebsite')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Website Source Dialog */}
      <Dialog open={addWebsiteDialogOpen} onOpenChange={setAddWebsiteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('websites.addWebsite')}</DialogTitle>
            <DialogDescription>
              {t('websites.addWebsiteHint')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t('websites.name')}</label>
              <Input
                value={newWebsiteName}
                onChange={(e) => setNewWebsiteName(e.target.value)}
                placeholder={t('websites.namePlaceholder')}
                className="mt-1"
              />
            </div>
            <div>
              <label className="text-sm font-medium">{t('websites.url')}</label>
              <Input
                value={newWebsiteUrl}
                onChange={(e) => setNewWebsiteUrl(e.target.value)}
                placeholder={t('websites.urlPlaceholder')}
                className="mt-1"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t('websites.rssFeedHint')}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddWebsiteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={addWebsiteSource}>
              {t('websites.addWebsite')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('websites.deleteConfirm')}</DialogTitle>
            <DialogDescription>
              {t('websites.deleteWarning')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDelete}>
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Website Source Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t('common.edit')} {editingSource?.name}</DialogTitle>
            <DialogDescription>
              {t('websites.editSourceHint', { name: editingSource?.name })}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="text-sm font-medium">{t('websites.customPrompt')}</label>
              <Textarea
                value={editPrompt}
                onChange={(e) => setEditPrompt(e.target.value)}
                placeholder={t('websites.promptPlaceholder')}
                className="mt-1 min-h-[150px] font-mono text-sm whitespace-pre-wrap break-all"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t('websites.promptHint')}
            </p>
            <div>
              <label className="text-sm font-medium">{t('websites.cookies')}</label>
              <Textarea
                value={editCookies}
                onChange={(e) => setEditCookies(e.target.value)}
                placeholder={t('websites.cookiesPlaceholder')}
                className="mt-1 min-h-[100px] font-mono text-xs whitespace-pre-wrap break-all"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t('websites.cookiesHint')}
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={savePrompt}>
              {t('common.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
    </TooltipProvider>
  );
};

export default Websites;
