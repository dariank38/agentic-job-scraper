import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import {
  Mail,
  MessageSquare,
  Calendar,
  Briefcase,
  CheckCircle2,
  Search,
  Download,
  Code2,
  FileText,
  Languages,
  MessagesSquare,
  Building2,
  MapPin,
  ExternalLink,
  Copy,
  Check,
  ScrollText,
  Loader2,
  Sparkles,
  Star,
  CheckCircle,
  XCircle,
  TrendingUp,
} from 'lucide-react';
import api from '@/services/api';
import type { Job } from '@/services/api';
import { useToast, useWebSocketProgress } from '@/components/Layout';

const getInitials = (name: string) => {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

const Jobs = () => {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [loadingActions, setLoadingActions] = useState<Set<string>>(new Set());
  const [total, setTotal] = useState(0);
  const [jobNotes, setJobNotes] = useState('');
  const [copiedMsg, setCopiedMsg] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [jobToDelete, setJobToDelete] = useState<number | null>(null);
  const [bulkDeleteDialogOpen, setBulkDeleteDialogOpen] = useState(false);
  const [selectedJobIds, setSelectedJobIds] = useState<Set<number>>(new Set());
  const [resumeDialogOpen, setResumeDialogOpen] = useState(false);
  const [resumeTab, setResumeTab] = useState<'generate' | 'enhance' | 'score'>('generate');
  const [resumeJobTitle, setResumeJobTitle] = useState('');
  // Generate tab
  const [generatedText, setGeneratedText] = useState('');
  const [generateLoading, setGenerateLoading] = useState(false);
  // Enhance tab
  const [userResumeInput, setUserResumeInput] = useState('');
  const [enhancedText, setEnhancedText] = useState('');
  const [enhanceLoading, setEnhanceLoading] = useState(false);
  // Score tab
  const [scoreResumeInput, setScoreResumeInput] = useState('');
  const [scoreResult, setScoreResult] = useState<null | {
    score: number; level: string; summary: string;
    matched_skills: string[]; missing_skills: string[];
    strengths: string[]; improvements: string[];
  }>(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [resumeProvider, setResumeProvider] = useState<{ provider: string; model: string; nvidia_configured: boolean } | null>(null);
  const appliedFilter = searchParams.get('is_applied');
  const favoriteFilter = searchParams.get('is_favorite');
  const sourceFilter = searchParams.get('source_type');
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');
  const jobIdParam = searchParams.get('jobId');
  const { showToast } = useToast();
  const { resumeGenerating } = useWebSocketProgress();

  useEffect(() => {
    loadJobs();
  }, [offset, searchQuery, appliedFilter, favoriteFilter, sourceFilter]);

  useEffect(() => {
    if (jobIdParam && jobs.length > 0) {
      const jobToSelect = jobs.find(j => j.id === parseInt(jobIdParam));
      if (jobToSelect) {
        setSelectedJob(jobToSelect);
        // Clear the param after selecting
        setSearchParams({});
      }
    }
  }, [jobIdParam, jobs]);

  const loadJobs = async () => {
    try {
      const params: any = { limit, offset };
      if (searchQuery) params.search = searchQuery;
      if (appliedFilter) params.is_applied = appliedFilter;
      if (favoriteFilter) params.is_favorite = favoriteFilter;
      if (sourceFilter) params.source_type = sourceFilter;
      const data = await api.getJobs(params);
      setJobs(data.jobs);
      setTotal(data.total || 0);
      if (data.jobs.length > 0 && !selectedJob) {
        setSelectedJob(data.jobs[0]);
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToLoad')} ${t('jobs.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    }
  };

  const handleNext = () => {
    const params = new URLSearchParams(searchParams);
    params.set('offset', (offset + limit).toString());
    setSearchParams(params);
  };

  const handlePrevious = () => {
    const params = new URLSearchParams(searchParams);
    params.set('offset', Math.max(0, offset - limit).toString());
    setSearchParams(params);
  };

  const handleFirst = () => {
    const params = new URLSearchParams(searchParams);
    params.set('offset', '0');
    setSearchParams(params);
  };

  const handleLast = () => {
    const params = new URLSearchParams(searchParams);
    const lastOffset = Math.floor((total - 1) / limit) * limit;
    params.set('offset', lastOffset.toString());
    setSearchParams(params);
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

  const clearFilters = () => {
    setSearchParams({});
    setSearchQuery('');
    setSearchInput('');
  };

  const applyAppliedFilter = (value: string) => {
    const params = new URLSearchParams(searchParams);
    params.delete('offset');
    if (value) params.set('is_applied', value);
    else params.delete('is_applied');
    setSearchParams(params);
  };

  const applySourceFilter = (value: string) => {
    const params = new URLSearchParams(searchParams);
    params.delete('offset');
    if (value) params.set('source_type', value);
    else params.delete('source_type');
    setSearchParams(params);
  };

  const applyFavoriteFilter = (value: string) => {
    const params = new URLSearchParams(searchParams);
    params.delete('offset');
    if (value) params.set('is_favorite', value);
    else params.delete('is_favorite');
    setSearchParams(params);
  };

  const toggleFavorite = async (id: number) => {
    const job = jobs.find(j => j.id === id);
    const nextFavorite = !job?.is_favorite;
    // Optimistic update
    setJobs(prevJobs => prevJobs.map(j => j.id === id ? { ...j, is_favorite: nextFavorite } : j));
    if (selectedJob?.id === id) {
      setSelectedJob(prev => prev ? { ...prev, is_favorite: nextFavorite } : null);
    }
    try {
      await withLoading(`favorite-${id}`, () => api.toggleJobFavorite(id));
      showToast('success', nextFavorite ? t('jobs.addedToFavorites') : t('jobs.removedFromFavorites'));
    } catch (e: any) {
      let errorMessage = `${t('common.failedToToggle')} ${t('jobs.favoriteStatus')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
      loadJobs();
    }
  };

  const toggleApplied = async (id: number) => {
    const job = jobs.find(j => j.id === id);
    if (job?.is_applied) {
      showToast('warning', t('jobs.alreadyApplied'));
      return;
    }
    // Optimistic update
    setJobs(prevJobs => prevJobs.map(j => j.id === id ? { ...j, is_applied: true } : j));
    if (selectedJob?.id === id) {
      setSelectedJob(prev => prev ? { ...prev, is_applied: true } : null);
    }
    try {
      await withLoading(`toggle-${id}`, () => api.toggleJobApplied(id, jobNotes));
      loadJobs();
      setJobNotes('');
      showToast('success', t('jobs.markedAsApplied'));
    } catch (e: any) {
      let errorMessage = `${t('common.failedToToggle')} ${t('jobs.applicationStatus')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
      // Revert on error
      loadJobs();
    }
  };

  const deleteJob = async (id: number) => {
    setJobToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteJob = async () => {
    if (!jobToDelete) return;
    try {
      await api.deleteJob(jobToDelete);
      setJobs(prevJobs => prevJobs.filter(j => j.id !== jobToDelete));
      if (selectedJob?.id === jobToDelete) {
        setSelectedJob(jobs.find(j => j.id !== jobToDelete) || null);
      }
      showToast('success', t('jobs.deletedSuccessfully'));
      setDeleteDialogOpen(false);
      setJobToDelete(null);
    } catch (e: any) {
      let errorMessage = `${t('common.failedToDelete')} ${t('jobs.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    }
  };

  const toggleJobSelection = (id: number) => {
    setSelectedJobIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectAllJobs = () => {
    setSelectedJobIds(new Set(jobs.map(j => j.id)));
  };

  const clearJobSelection = () => {
    setSelectedJobIds(new Set());
  };

  const handleBulkDeleteJobs = async () => {
    if (selectedJobIds.size === 0) return;
    try {
      const data = await api.bulkDeleteJobs(Array.from(selectedJobIds));
      if (data.success) {
        showToast('success', t('jobs.bulkDeletedSuccessfully', { count: data.deleted }));
        setSelectedJobIds(new Set());
        setBulkDeleteDialogOpen(false);
        if (selectedJob && selectedJobIds.has(selectedJob.id)) {
          setSelectedJob(null);
        }
        loadJobs();
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToDelete')} ${t('jobs.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    }
  };

  const exportJobs = () => {
    const headers = [
      t('jobs.jobTitle'),
      t('jobs.company'),
      t('jobs.location'),
      t('jobs.roleType'),
      t('jobs.skills'),
      t('jobs.contact'),
      t('jobs.remote'),
      t('jobs.applied'),
      t('common.channels'),
      t('jobs.postedDate'),
    ];
    const rows = jobs.map(job => {
      const skillsStr = Array.isArray(job.skills) ? job.skills.join(', ') : '';
      return [
        job.title || '',
        job.company || '',
        job.location || '',
        job.role_type || '',
        skillsStr,
        job.contact || '',
        job.is_remote ? t('common.yes') : t('common.no'),
        job.is_applied ? t('common.yes') : t('common.no'),
        job.channel?.username || t('common.unknown'),
        job.message.date ? new Date(job.message.date).toLocaleDateString() : ''
      ];
    });

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `jobs_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('success', t('jobs.exportedJobs', { count: jobs.length }));
  };

  const openResumeDialog = (job: Job, tab: 'generate' | 'enhance' | 'score' = 'generate') => {
    setResumeJobTitle(job.title || job.company || t('jobs.untitledJob'));
    setResumeTab(tab);
    setResumeDialogOpen(true);
    api.getResumeProvider().then(setResumeProvider).catch(() => {});
  };

  const handleGenerateResume = async (job: Job) => {
    setGenerateLoading(true);
    try {
      await api.generateResume(job.id, (chunk) => setGeneratedText(prev => prev + chunk));
    } catch (e: any) {
      showToast('error', e.message || t('jobs.resumeGenerationFailed'));
    } finally {
      setGenerateLoading(false);
    }
  };

  const handleEnhanceResume = async (job: Job) => {
    if (!userResumeInput.trim()) { showToast('error', t('jobs.resumePasteFirst')); return; }
    setEnhancedText('');
    setEnhanceLoading(true);
    try {
      await api.enhanceResume(job.id, userResumeInput, (chunk) => setEnhancedText(prev => prev + chunk));
    } catch (e: any) {
      showToast('error', e.message || t('jobs.resumeEnhancementFailed'));
    } finally {
      setEnhanceLoading(false);
    }
  };

  const handleScoreResume = async (job: Job) => {
    if (!scoreResumeInput.trim()) { showToast('error', t('jobs.resumePasteFirst')); return; }
    setScoreResult(null);
    setScoreLoading(true);
    try {
      const result = await api.scoreResume(job.id, scoreResumeInput);
      setScoreResult(result);
    } catch (e: any) {
      showToast('error', e.message || t('jobs.resumeScoringFailed'));
    } finally {
      setScoreLoading(false);
    }
  };

  const copyText = (text: string) => {
    navigator.clipboard.writeText(text);
    showToast('success', t('jobs.resumeCopied'));
  };

  const downloadText = (text: string, prefix: string) => {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${prefix}_${resumeJobTitle.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
  };

  const scoreLevelColor = (level: string) => {
    if (level === 'excellent') return 'text-green-600';
    if (level === 'good') return 'text-blue-600';
    if (level === 'fair') return 'text-yellow-600';
    return 'text-red-600';
  };

  const scoreBarColor = (score: number) => {
    if (score >= 90) return 'bg-green-500';
    if (score >= 70) return 'bg-blue-500';
    if (score >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const getSkills = (job: Job) => {
    const skills = job.skills;
    if (Array.isArray(skills)) {
      return skills;
    } else if (typeof skills === 'string') {
      return skills.split('\n').filter(s => s.trim());
    }
    return [];
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('jobs.title')}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {t('jobs.foundCount', { count: total })}
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" onClick={exportJobs} disabled={jobs.length === 0}>
            <Download className="w-4 h-4 mr-1.5" />
            {t('common.exportCsv')}
          </Button>
        </div>
      </div>

      {(jobs.length > 0 || searchQuery) ? (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Left Sidebar - Job List */}
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="space-y-3">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    placeholder={t('jobs.searchPlaceholder')}
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { const p = new URLSearchParams(searchParams); p.delete('offset'); setSearchParams(p); setSearchQuery(searchInput); } }}
                    className="pl-9"
                  />
                </div>
                {/* Filters */}
                <div className="flex flex-col sm:flex-row gap-2">
                  <select
                    value={appliedFilter || ''}
                    onChange={(e) => applyAppliedFilter(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="">{t('common.allStatus')}</option>
                    <option value="true">{t('jobs.applied')}</option>
                    <option value="false">{t('jobs.notApplied')}</option>
                  </select>
                  <select
                    value={sourceFilter || ''}
                    onChange={(e) => applySourceFilter(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="">{t('jobs.allSources')}</option>
                    <option value="telegram">{t('jobs.sourceTelegram')}</option>
                    <option value="website">{t('jobs.sourceWebsite')}</option>
                  </select>
                  <select
                    value={favoriteFilter || ''}
                    onChange={(e) => applyFavoriteFilter(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="">{t('jobs.allFavorites')}</option>
                    <option value="true">{t('jobs.favorites')}</option>
                    <option value="false">{t('jobs.notFavorites')}</option>
                  </select>
                  {(appliedFilter || favoriteFilter || sourceFilter || searchQuery) && (
                    <Button variant="ghost" size="sm" onClick={clearFilters}>
                      {t('common.clear')}
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {/* Bulk Actions */}
              {jobs.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 px-4 pt-3 pb-2 border-b">
                  <Button variant="outline" size="sm" onClick={selectAllJobs}>
                    {t('common.selectAll')}
                  </Button>
                  <Button variant="outline" size="sm" onClick={clearJobSelection}>
                    {t('common.clearSelection')}
                  </Button>
                  {selectedJobIds.size > 0 && (
                    <>
                      <span className="text-sm text-muted-foreground">
                        {t('common.selectedCount', { count: selectedJobIds.size })}
                      </span>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => setBulkDeleteDialogOpen(true)}
                      >
                        {t('common.bulkDelete')}
                      </Button>
                    </>
                  )}
                </div>
              )}
              <div className="px-4 pb-4 space-y-1">
                {jobs.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-8">{t('jobs.noJobsMatch')}</p>
                ) : (
                  jobs.map((job) => {
                    const isSelected = selectedJob?.id === job.id;
                    const skills = getSkills(job);
                    return (
                      <div
                        key={job.id}
                        onClick={() => setSelectedJob(job)}
                        className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-primary/5 border border-primary/20 shadow-sm'
                            : 'hover:bg-gray-50 border border-transparent'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedJobIds.has(job.id)}
                          onChange={(e) => { e.stopPropagation(); toggleJobSelection(job.id); }}
                          className="mt-2.5 w-4 h-4 accent-primary shrink-0"
                        />
                        {/* Avatar */}
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-semibold shrink-0 ${
                          isSelected
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-gray-200 text-gray-700'
                        }`}>
                          {getInitials(job.company || job.title || t('jobs.untitledJob'))}
                        </div>
                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className={`font-medium text-base truncate ${isSelected ? 'text-primary' : ''}`}>
                              {job.title || (job.message?.text?.substring(0, 60) + (job.message?.text && job.message.text.length > 60 ? '...' : '')) || t('jobs.untitledJob')}
                            </span>
                            {job.is_favorite && (
                              <Star className="w-4 h-4 text-amber-500 fill-amber-500 shrink-0" />
                            )}
                            {job.is_applied && (
                              <Badge variant="default" className="text-xs h-5 px-1.5">{t('jobs.applied')}</Badge>
                            )}
                            {job.role_type && (
                              <>
                                {job.role_type.split(/[|,]/).slice(0, 3).map((role, idx) => (
                                  <Badge
                                    key={idx}
                                    variant="secondary"
                                    className="text-xs h-5 px-1.5 bg-blue-50 text-blue-700 border-blue-200"
                                  >
                                    {role.trim()}
                                  </Badge>
                                ))}
                              </>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 truncate">
                            {job.company || t('jobs.unknownCompany')}
                          </p>
                          {skills.length > 0 && (
                            <div className="flex gap-1 mt-1.5 flex-wrap">
                              {skills.slice(0, 3).map((skill, idx) => (
                                <span key={idx} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded-md">
                                  {skill}
                                </span>
                              ))}
                              {skills.length > 3 && (
                                <span className="text-[10px] text-gray-400">+{skills.length - 3}</span>
                              )}
                            </div>
                          )}
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-gray-400">
                            <span className="flex items-center gap-1">
                              <MessageSquare className="w-3 h-3" />
                              {job.channel_name || job.channel?.username || t('common.unknown')}
                            </span>
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              {job.message?.date
                                ? new Date(job.message.date).toLocaleDateString()
                                : t('common.unknown')
                              }
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              {/* Pagination */}
              {jobs.length > 0 && (
                <div className="px-4 pb-4 pt-0">
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t">
                    <div className="flex gap-2 w-full sm:w-auto">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleFirst()}
                        disabled={offset === 0}
                        className="flex-1 sm:flex-none"
                      >
                        {t('common.first')}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handlePrevious}
                        disabled={offset === 0}
                        className="flex-1 sm:flex-none"
                      >
                        {t('common.previous')}
                      </Button>
                    </div>
                    <span className="text-sm text-muted-foreground text-center">
                      {t('common.page')} {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)}
                    </span>
                    <div className="flex gap-2 w-full sm:w-auto">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleNext}
                        disabled={offset + limit >= total}
                        className="flex-1 sm:flex-none"
                      >
                        {t('common.next')}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleLast()}
                        disabled={offset + limit >= total}
                        className="flex-1 sm:flex-none"
                      >
                        {t('common.last')}
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Right Column - Job Details */}
          <Card className="md:col-span-3 overflow-visible">
            <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
              {selectedJob ? (
                <div className="space-y-6">
                  {/* Header Section */}
                  <div className="flex items-start gap-3 sm:gap-4">
                    <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-lg sm:text-xl font-bold text-primary-foreground shrink-0">
                      {getInitials(selectedJob.company || selectedJob.title || t('jobs.untitledJob'))}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap gap-2 sm:gap-2.5 mb-2 max-w-full">
                        <Badge variant={selectedJob.is_applied ? 'default' : 'secondary'} className="text-sm px-3 py-1 shrink-0">
                          {selectedJob.is_applied ? t('jobs.applied') : t('jobs.notApplied')}
                        </Badge>
                        {selectedJob.source_type && (
                          <Badge variant="outline" className="text-xs sm:text-sm px-2.5 py-0.5 sm:px-3 sm:py-1 shrink-0">
                            {selectedJob.source_type === 'telegram' ? t('common.telegram') : t('common.website')}
                          </Badge>
                        )}
                        {selectedJob.is_remote && (
                          <Badge className="bg-teal-100 text-teal-700 hover:bg-teal-100 text-sm px-3 py-1 shrink-0">{t('jobs.remote')}</Badge>
                        )}
                        {selectedJob.confidence && (
                          <Badge variant="outline" className="text-xs sm:text-sm px-2.5 py-0.5 sm:px-3 sm:py-1 shrink-0">
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                            {selectedJob.confidence}
                          </Badge>
                        )}
                      </div>
                      <h2 className="text-lg sm:text-xl font-bold truncate">
                        {selectedJob.title || (selectedJob.message?.text?.substring(0, 80) + (selectedJob.message?.text && selectedJob.message.text.length > 80 ? '...' : '')) || t('jobs.untitledJob')}
                      </h2>
                      <p className="text-xs sm:text-sm text-muted-foreground flex items-center gap-1 mt-0.5 flex-wrap">
                        <Building2 className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                        <span className="truncate">{selectedJob.company || t('jobs.unknownCompany')}</span>
                        {selectedJob.location && (
                          <>
                            <span className="text-gray-300 hidden sm:inline">|</span>
                            <span className="flex items-center gap-1 sm:hidden w-full mt-0.5">
                              <MapPin className="w-3 h-3" />
                              {selectedJob.location}
                            </span>
                            <span className="hidden sm:flex items-center gap-1">
                              <MapPin className="w-3.5 h-3.5" />
                              {selectedJob.location}
                            </span>
                          </>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex flex-wrap gap-2 pt-2">
                    {!selectedJob.is_applied && (
                      <Input
                        placeholder={t('jobs.addNotes')}
                        value={jobNotes}
                        onChange={(e) => setJobNotes(e.target.value)}
                        className="flex-1 min-w-32"
                      />
                    )}
                    <Button
                      size="sm"
                      variant={selectedJob.is_applied ? 'default' : 'outline'}
                      onClick={() => toggleApplied(selectedJob.id)}
                      disabled={loadingActions.has(`toggle-${selectedJob.id}`)}
                    >
                      {selectedJob.is_applied ? t('jobs.applied') + ' ✓' : t('jobs.markApplied')}
                    </Button>
                    <Button
                      size="sm"
                      variant={selectedJob.is_favorite ? 'default' : 'outline'}
                      className={selectedJob.is_favorite ? 'bg-amber-500 hover:bg-amber-600 text-white' : 'border-amber-300 text-amber-600 hover:bg-amber-50'}
                      onClick={() => toggleFavorite(selectedJob.id)}
                      disabled={loadingActions.has(`favorite-${selectedJob.id}`)}
                    >
                      <Star className={`w-3.5 h-3.5 mr-1.5 ${selectedJob.is_favorite ? 'fill-white' : ''}`} />
                      {selectedJob.is_favorite ? t('jobs.favorited') : t('jobs.addToFavorites')}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-purple-200 text-purple-700 hover:bg-purple-50"
                      onClick={() => openResumeDialog(selectedJob, 'generate')}
                      disabled={!!resumeGenerating}
                      title={resumeGenerating ? t('jobs.resumeGeneratingFor', { title: resumeGenerating.job_title }) : undefined}
                    >
                      {resumeGenerating ? (
                        <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />{t('jobs.generatingResume')}</>
                      ) : (
                        <><ScrollText className="w-3.5 h-3.5 mr-1.5" />{t('jobs.generateResume')}</>
                      )}
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => deleteJob(selectedJob.id)}
                    >
                      {t('jobs.deleteJob')}
                    </Button>
                  </div>

                  <Separator />

                  {/* Contact Link */}
                  {selectedJob.contact && (
                    <div className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-amber-50 border border-amber-100">
                      <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-amber-500 flex items-center justify-center shrink-0">
                        <Mail className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] sm:text-xs text-amber-600 font-medium">{t('jobs.contact')}</p>
                        <p className="text-xs sm:text-sm text-gray-900 truncate">{selectedJob.contact}</p>
                      </div>
                    </div>
                  )}

                  {/* Company Link */}
                  {selectedJob.company_link && (
                    <a href={selectedJob.company_link} target="_blank" rel="noopener noreferrer"
                       className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors group">
                      <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-gray-900 flex items-center justify-center shrink-0">
                        <ExternalLink className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] sm:text-xs text-gray-500 font-medium">{t('jobs.companyWebsite')}</p>
                        <p className="text-xs sm:text-sm text-gray-900 truncate group-hover:text-primary transition-colors">{selectedJob.company_link}</p>
                      </div>
                    </a>
                  )}

                  {/* Skills */}
                  {selectedJob.skills && getSkills(selectedJob).length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2 sm:mb-3">
                        <Code2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                        <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('jobs.skills')}</h3>
                      </div>
                      <div className="flex flex-wrap gap-2.5">
                        {getSkills(selectedJob).map((skill, idx) => (
                          <Badge key={idx} variant="secondary" className="px-4 py-1.5 text-sm font-medium bg-primary/10 text-primary hover:bg-primary/20">
                            {skill}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Role Type */}
                  {selectedJob.role_type && (
                    <div className="bg-blue-50/50 rounded-lg p-3 border border-blue-100">
                      <div className="flex items-center gap-2 mb-2">
                        <Briefcase className="w-4 h-4 text-blue-600" />
                        <h3 className="text-xs sm:text-sm font-semibold text-blue-900">{t('jobs.roleType')}</h3>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selectedJob.role_type.split(/[|,]/).map((role, idx) => (
                          <Badge
                            key={idx}
                            className="bg-blue-100 text-blue-800 hover:bg-blue-200 border-blue-200 text-sm px-3 py-1"
                          >
                            {role.trim()}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Summary */}
                  {selectedJob.summary && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                        <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('jobs.summary')}</h3>
                      </div>
                      <p className="text-sm text-gray-600 leading-relaxed break-words">{selectedJob.summary}</p>
                    </div>
                  )}

                  {/* English Translation */}
                  {selectedJob.translated_text && (
                    <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2 sm:mb-3">
                        <Languages className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-blue-600" />
                        <h3 className="text-xs sm:text-sm font-semibold text-blue-900">{t('jobs.englishTranslation')}</h3>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">{selectedJob.translated_text}</p>
                    </div>
                  )}

                  {/* Original Message */}
                  <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2 sm:mb-3">
                      <MessagesSquare className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-gray-600" />
                      <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('jobs.originalMessage')}</h3>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5 ml-auto"
                        onClick={() => {
                          const text = selectedJob?.message?.text?.replace(/<[^>]*>/g, '') || '';
                          navigator.clipboard.writeText(text);
                          setCopiedMsg(true);
                          setTimeout(() => setCopiedMsg(false), 2000);
                        }}
                      >
                        {copiedMsg ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-gray-500" />}
                      </Button>
                    </div>
                    <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words prose prose-sm max-w-none"
                         dangerouslySetInnerHTML={{ __html: selectedJob.message?.text || t('jobs.noTextContent') }} />
                    <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <MessageSquare className="w-3 h-3" />
                        {selectedJob.channel_name || selectedJob.channel?.username || t('common.unknown')}
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {selectedJob.message?.date ? new Date(selectedJob.message.date).toLocaleString() : t('common.unknown')}
                      </span>
                    </div>
                  </div>

                  {/* Notes */}
                  {selectedJob.notes !== undefined && (
                    <div className="bg-yellow-50/50 border border-yellow-100 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-yellow-600" />
                        <h3 className="text-xs sm:text-sm font-semibold text-yellow-900">{t('jobs.notes')}</h3>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed break-words">{selectedJob.notes || t('jobs.noNotes')}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                  <Briefcase className="w-12 h-12 mb-3 opacity-50" />
                  <p className="text-sm">{t('jobs.selectJob')}</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Left Column - Jobs List */}
          <Card className="md:col-span-1">
            <CardHeader>
              <CardTitle className="text-lg">{t('jobs.title')}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-4 pb-4 space-y-1">
                <p className="text-sm text-gray-500 text-center py-8">{t('jobs.noJobsFound')}</p>
              </div>
            </CardContent>
          </Card>

          {/* Right Column - Job Details */}
          <Card className="md:col-span-3">
            <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
              <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                <Briefcase className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm">{t('jobs.selectJob')}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Resume Dialog — Generate / Enhance / Score */}
      <Dialog open={resumeDialogOpen} onOpenChange={setResumeDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] flex flex-col">
          <DialogHeader className="pb-0">
            <DialogTitle className="flex items-center gap-2">
              <ScrollText className="w-4 h-4 text-purple-600" />
              {t('jobs.resumeTitle')}
              {resumeProvider && (
                <span className={`ml-1 text-xs font-medium px-2 py-0.5 rounded-full ${resumeProvider.provider === 'nvidia' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>
                  {resumeProvider.provider === 'nvidia' ? t('jobs.resumeProviderNvidia') : t('jobs.resumeProviderOllama')} · {resumeProvider.model}
                </span>
              )}
            </DialogTitle>
            <DialogDescription>
              {t('jobs.resumeFor')} <span className="font-medium">{resumeJobTitle}</span>
            </DialogDescription>
          </DialogHeader>

          <Tabs value={resumeTab} onValueChange={(v) => setResumeTab(v as any)} className="flex-1 flex flex-col min-h-0">
            <TabsList className="grid grid-cols-3 w-full">
              <TabsTrigger value="generate">
                <ScrollText className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeGenerate')}
              </TabsTrigger>
              <TabsTrigger value="enhance">
                <Sparkles className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeEnhance')}
              </TabsTrigger>
              <TabsTrigger value="score">
                <Star className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeScore')}
              </TabsTrigger>
            </TabsList>

            {/* ── GENERATE TAB ── */}
            <TabsContent value="generate" className="flex-1 flex flex-col min-h-0 mt-3 gap-3">
              <p className="text-xs text-muted-foreground">{t('jobs.resumeGenerateDesc')}</p>
              <div className="flex-1 overflow-y-auto">
                <pre className="text-sm text-gray-800 whitespace-pre-wrap break-words leading-relaxed font-sans bg-gray-50 rounded-lg p-4 border min-h-32">
                  {generatedText || (generateLoading ? t('jobs.generatingResume') : t('jobs.resumeEmptyGenerate'))}
                </pre>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                <Button variant="outline" size="sm" onClick={() => setResumeDialogOpen(false)}>{t('jobs.resumeClose')}</Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-purple-200 text-purple-700 hover:bg-purple-50"
                  onClick={() => { if (selectedJob) { setGeneratedText(''); void handleGenerateResume(selectedJob); } }}
                  disabled={generateLoading || !!resumeGenerating}
                >
                  {generateLoading ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />{t('jobs.generatingResume')}</> : <><ScrollText className="w-3.5 h-3.5 mr-1.5" />{generatedText ? t('jobs.regenerateResume') : t('jobs.resumeGenerate')}</>}
                </Button>
                {generatedText && (
                  <>
                    <Button variant="outline" size="sm" onClick={() => copyText(generatedText)}>
                      <Copy className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeCopy')}
                    </Button>
                    <Button size="sm" onClick={() => downloadText(generatedText, 'resume')}>
                      <Download className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeDownload')}
                    </Button>
                  </>
                )}
              </div>
            </TabsContent>

            {/* ── ENHANCE TAB ── */}
            <TabsContent value="enhance" className="flex-1 flex flex-col min-h-0 mt-3 gap-3">
              <p className="text-xs text-muted-foreground">{t('jobs.resumeEnhanceDesc')}</p>
              <Textarea
                placeholder={t('jobs.resumePasteCurrent')}
                value={userResumeInput}
                onChange={(e) => setUserResumeInput(e.target.value)}
                className="min-h-[120px] text-sm resize-none"
              />
              <Button
                size="sm"
                className="bg-purple-600 hover:bg-purple-700 text-white self-start"
                onClick={() => selectedJob && handleEnhanceResume(selectedJob)}
                disabled={enhanceLoading || !userResumeInput.trim()}
              >
                {enhanceLoading ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />{t('jobs.resumeEnhancing')}</> : <><Sparkles className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeEnhanceBtn')}</>}
              </Button>
              {(enhancedText || enhanceLoading) && (
                <div className="flex-1 overflow-y-auto">
                  <pre className="text-sm text-gray-800 whitespace-pre-wrap break-words leading-relaxed font-sans bg-gray-50 rounded-lg p-4 border min-h-24">
                    {enhancedText || t('jobs.resumeEmptyEnhance')}
                  </pre>
                </div>
              )}
              {enhancedText && (
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => copyText(enhancedText)}>
                    <Copy className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeCopy')}
                  </Button>
                  <Button size="sm" onClick={() => downloadText(enhancedText, 'enhanced_resume')}>
                    <Download className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeDownload')}
                  </Button>
                </div>
              )}
            </TabsContent>

            {/* ── SCORE TAB ── */}
            <TabsContent value="score" className="flex-1 flex flex-col min-h-0 mt-3 gap-3">
              <p className="text-xs text-muted-foreground">{t('jobs.resumeScoreDesc')}</p>
              <Textarea
                placeholder={t('jobs.resumePasteHere')}
                value={scoreResumeInput}
                onChange={(e) => setScoreResumeInput(e.target.value)}
                className="min-h-[120px] text-sm resize-none"
              />
              <Button
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white self-start"
                onClick={() => selectedJob && handleScoreResume(selectedJob)}
                disabled={scoreLoading || !scoreResumeInput.trim()}
              >
                {scoreLoading ? <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />{t('jobs.resumeScoring')}</> : <><TrendingUp className="w-3.5 h-3.5 mr-1.5" />{t('jobs.resumeScoreBtn')}</>}
              </Button>
              {scoreResult && (
                <div className="flex-1 overflow-y-auto space-y-4">
                  {/* Score banner */}
                  <div className="flex items-center gap-4 p-4 rounded-xl bg-gray-50 border">
                    <div className="text-center">
                      <div className={`text-4xl font-bold ${scoreLevelColor(scoreResult.level)}`}>{scoreResult.score}</div>
                      <div className="text-xs text-gray-500 mt-0.5">{t('jobs.resumeOutOf100')}</div>
                    </div>
                    <div className="flex-1">
                      <div className="w-full bg-gray-200 rounded-full h-2.5 mb-2">
                        <div className={`h-2.5 rounded-full transition-all ${scoreBarColor(scoreResult.score)}`} style={{ width: `${scoreResult.score}%` }} />
                      </div>
                      <p className={`text-sm font-semibold capitalize ${scoreLevelColor(scoreResult.level)}`}>{scoreResult.level}</p>
                      <p className="text-xs text-gray-600 mt-0.5">{scoreResult.summary}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    {/* Matched skills */}
                    <div className="rounded-lg border p-3">
                      <div className="flex items-center gap-1.5 mb-2 text-green-700 font-medium text-xs">
                        <CheckCircle className="w-3.5 h-3.5" />{t('jobs.resumeMatchedSkills')}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {scoreResult.matched_skills.map((s, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 bg-green-50 text-green-700 border border-green-200 rounded-full">{s}</span>
                        ))}
                      </div>
                    </div>
                    {/* Missing skills */}
                    <div className="rounded-lg border p-3">
                      <div className="flex items-center gap-1.5 mb-2 text-red-600 font-medium text-xs">
                        <XCircle className="w-3.5 h-3.5" />{t('jobs.resumeMissingSkills')}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {scoreResult.missing_skills.map((s, i) => (
                          <span key={i} className="text-xs px-2 py-0.5 bg-red-50 text-red-700 border border-red-200 rounded-full">{s}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                  {/* Strengths */}
                  <div className="rounded-lg border p-3">
                    <div className="flex items-center gap-1.5 mb-2 text-blue-700 font-medium text-xs">
                      <Star className="w-3.5 h-3.5" />{t('jobs.resumeStrengths')}
                    </div>
                    <ul className="space-y-1">
                      {scoreResult.strengths.map((s, i) => <li key={i} className="text-xs text-gray-700">• {s}</li>)}
                    </ul>
                  </div>
                  {/* Improvements */}
                  <div className="rounded-lg border p-3">
                    <div className="flex items-center gap-1.5 mb-2 text-amber-600 font-medium text-xs">
                      <TrendingUp className="w-3.5 h-3.5" />{t('jobs.resumeImprovements')}
                    </div>
                    <ul className="space-y-1">
                      {scoreResult.improvements.map((s, i) => <li key={i} className="text-xs text-gray-700">• {s}</li>)}
                    </ul>
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('jobs.deleteConfirm')}</DialogTitle>
            <DialogDescription>
              {t('jobs.deleteWarning')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDeleteJob}>
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Confirmation Dialog */}
      <Dialog open={bulkDeleteDialogOpen} onOpenChange={setBulkDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('jobs.bulkDeleteConfirm')}</DialogTitle>
            <DialogDescription>
              {t('jobs.bulkDeleteWarning', { count: selectedJobIds.size })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={handleBulkDeleteJobs}>
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

    </>
  );
};

export default Jobs;
