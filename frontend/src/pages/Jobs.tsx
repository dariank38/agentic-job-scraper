import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Mail,
  MessageSquare,
  Calendar,
  Briefcase,
  Search,
  Download,
  Code2,
  FileText,
  MessagesSquare,
  Building2,
  MapPin,
  ExternalLink,
  Copy,
  Check,
  ScrollText,
  Loader2,
  Star,
  Send,
  Globe,
} from 'lucide-react';
import api from '@/services/api';
import type { Job } from '@/services/api';
import { copyToClipboard } from '@/utils/clipboard';
import { useToast, useWebSocketProgress } from '@/components/Layout';

const getInitials = (name: string) => {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

const Jobs = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
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
      t('jobs.hrContact'),
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
        job.hr_contact || job.channel_contact || '',
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

  const openResumePage = (job: Job, tab: 'generate' | 'enhance' | 'score' = 'generate') => {
    const params = new URLSearchParams();
    params.set('jobId', job.id.toString());
    params.set('tab', tab);
    navigate(`/resume?${params.toString()}`);
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
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl mb-5 bg-gradient-to-br from-indigo-600 via-blue-600 to-cyan-600 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Briefcase className="w-5 h-5" />
              <h1 className="text-xl font-bold tracking-tight">{t('jobs.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{t('jobs.foundCount', { count: total })}</p>
          </div>
          <Button
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm w-full sm:w-auto"
            size="sm" onClick={exportJobs} disabled={jobs.length === 0}
          >
            <Download className="w-4 h-4 mr-1.5" />
            {t('common.exportCsv')}
          </Button>
        </div>
      </div>

      {(jobs.length > 0 || searchQuery) ? (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Left Sidebar - Job List */}
          <Card className="lg:col-span-2 shadow-sm">
            <CardHeader className="pb-3">
              <div className="space-y-3">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
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
                  <Select value={appliedFilter || ''} onValueChange={applyAppliedFilter}>
                    <SelectTrigger className="flex-1 h-9 text-sm">
                      <SelectValue placeholder={t('common.allStatus')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">{t('common.allStatus')}</SelectItem>
                      <SelectItem value="true">{t('jobs.applied')}</SelectItem>
                      <SelectItem value="false">{t('jobs.notApplied')}</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={sourceFilter || ''} onValueChange={applySourceFilter}>
                    <SelectTrigger className="flex-1 h-9 text-sm">
                      <SelectValue placeholder={t('jobs.allSources')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">{t('jobs.allSources')}</SelectItem>
                      <SelectItem value="telegram">{t('jobs.sourceTelegram')}</SelectItem>
                      <SelectItem value="website">{t('jobs.sourceWebsite')}</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select value={favoriteFilter || ''} onValueChange={applyFavoriteFilter}>
                    <SelectTrigger className="flex-1 h-9 text-sm">
                      <SelectValue placeholder={t('jobs.allFavorites')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">{t('jobs.allFavorites')}</SelectItem>
                      <SelectItem value="true">{t('jobs.favorites')}</SelectItem>
                      <SelectItem value="false">{t('jobs.notFavorites')}</SelectItem>
                    </SelectContent>
                  </Select>
                  {(appliedFilter || favoriteFilter || sourceFilter || searchQuery) && (
                    <Button variant="ghost" size="sm" onClick={clearFilters} className="shrink-0">
                      {t('common.clear')}
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {/* Bulk Actions */}
              {jobs.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 px-4 pt-2 pb-2 border-b">
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={selectAllJobs}>
                    {t('common.selectAll')}
                  </Button>
                  <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={clearJobSelection}>
                    {t('common.clearSelection')}
                  </Button>
                  {selectedJobIds.size > 0 && (
                    <>
                      <span className="text-xs text-muted-foreground bg-muted px-2 py-1 rounded-full">
                        {t('common.selectedCount', { count: selectedJobIds.size })}
                      </span>
                      <Button variant="destructive" size="sm" className="h-7 text-xs"
                        onClick={() => setBulkDeleteDialogOpen(true)}>
                        {t('common.bulkDelete')}
                      </Button>
                    </>
                  )}
                </div>
              )}
              <div className="divide-y">
                {jobs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                    <div className="w-12 h-12 rounded-2xl bg-muted flex items-center justify-center mb-3">
                      <Briefcase className="w-6 h-6 opacity-40" />
                    </div>
                    <p className="text-sm">{t('jobs.noJobsMatch')}</p>
                  </div>
                ) : (
                  jobs.map((job) => {
                    const isSelected = selectedJob?.id === job.id;
                    const skills = getSkills(job);
                    return (
                      <div
                        key={job.id}
                        onClick={() => setSelectedJob(job)}
                        className={`flex items-start gap-3 p-3 cursor-pointer transition-colors ${
                          isSelected ? 'bg-primary/5' : 'hover:bg-muted/40'
                        }`}
                      >
                        <Checkbox
                          checked={selectedJobIds.has(job.id)}
                          onCheckedChange={() => toggleJobSelection(job.id)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-2.5 shrink-0"
                        />
                        {/* Avatar */}
                        <div className={`w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold shrink-0 ${
                          isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                        }`}>
                          {getInitials(job.company || job.title || t('jobs.untitledJob'))}
                        </div>
                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className={`font-semibold text-sm truncate ${isSelected ? 'text-primary' : ''}`}>
                              {job.title || (job.message?.text?.substring(0, 60) + (job.message?.text && job.message.text.length > 60 ? '...' : '')) || t('jobs.untitledJob')}
                            </span>
                            {job.is_favorite && (
                              <Star className="w-4 h-4 text-amber-500 fill-amber-500 shrink-0" />
                            )}
                            {job.is_applied && (
                              <Badge variant="default" className="text-xs h-5 px-1.5">{t('jobs.applied')}</Badge>
                            )}
                            {job.published_to_jobees && (
                              <Badge className="text-xs h-5 px-1.5 bg-green-100 text-green-700 border-green-200 hover:bg-green-100">Jobees</Badge>
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
                          <p className="text-xs text-muted-foreground truncate">
                            {job.company || t('jobs.unknownCompany')}
                          </p>
                          {skills.length > 0 && (
                            <div className="flex gap-1 mt-1.5 flex-wrap">
                              {skills.slice(0, 3).map((skill, idx) => (
                                <Badge key={idx} variant="outline" className="text-[10px] px-1.5 py-0 font-normal">
                                  {skill}
                                </Badge>
                              ))}
                              {skills.length > 3 && (
                                <span className="text-[10px] text-muted-foreground self-center">+{skills.length - 3}</span>
                              )}
                            </div>
                          )}
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                            <span className="flex items-center gap-1">
                              {job.source_type === 'website' ? (
                                <Globe className="w-3 h-3" />
                              ) : (
                                <MessageSquare className="w-3 h-3" />
                              )}
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
          <Card className="md:col-span-3">
            <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
              <TooltipProvider delayDuration={400}>
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
                        {selectedJob.published_to_jobees && (
                          <Badge className="bg-green-100 text-green-700 hover:bg-green-100 text-sm px-3 py-1 shrink-0">
                            <Send className="w-3.5 h-3.5 mr-1.5" />
                            Jobees
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
                            <span className="text-muted-foreground/30 hidden sm:inline">|</span>
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
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="sm"
                          variant={selectedJob.is_applied ? 'default' : 'outline'}
                          onClick={() => toggleApplied(selectedJob.id)}
                          disabled={loadingActions.has(`toggle-${selectedJob.id}`)}
                        >
                          {selectedJob.is_applied ? t('jobs.applied') + ' ✓' : t('jobs.markApplied')}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{selectedJob.is_applied ? t('jobs.applied') : t('jobs.markApplied')}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
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
                      </TooltipTrigger>
                      <TooltipContent>{selectedJob.is_favorite ? t('jobs.favorited') : t('jobs.addToFavorites')}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-purple-200 text-purple-700 hover:bg-purple-50"
                          onClick={() => openResumePage(selectedJob, 'generate')}
                          disabled={!!resumeGenerating}
                        >
                          {resumeGenerating ? (
                            <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />{t('jobs.generatingResume')}</>
                          ) : (
                            <><ScrollText className="w-3.5 h-3.5 mr-1.5" />{t('jobs.generateResume')}</>
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{resumeGenerating ? t('jobs.resumeGeneratingFor', { title: resumeGenerating.job_title }) : t('jobs.generateResume')}</TooltipContent>
                    </Tooltip>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-green-200 text-green-700 hover:bg-green-50"
                          disabled={loadingActions.has(`publish-${selectedJob.id}`) || selectedJob.published_to_jobees}
                          onClick={async () => {
                            try {
                              const result = await api.publishJobToJobees(selectedJob.id);
                              if (result.success) {
                                showToast('success', `Published to Jobees: ${result.created} created, ${result.skipped} skipped`);
                                setJobs(prev => prev.map(j => j.id === selectedJob.id ? { ...j, published_to_jobees: true } : j));
                                setSelectedJob(prev => prev ? { ...prev, published_to_jobees: true } : null);
                              } else {
                                showToast('error', `Publish failed: ${result.errors?.join(', ') || 'unknown error'}`);
                              }
                            } catch (e: any) {
                              showToast('error', `Publish failed: ${e.message}`);
                            }
                          }}
                        >
                          {loadingActions.has(`publish-${selectedJob.id}`) ? (
                            <><Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />Publishing...</>
                          ) : selectedJob.published_to_jobees ? (
                            <><Send className="w-3.5 h-3.5 mr-1.5" />Published</>
                          ) : (
                            <><Send className="w-3.5 h-3.5 mr-1.5" />Publish to Jobees</>
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>{selectedJob.published_to_jobees ? 'Already published to Jobees' : 'Publish this job to Jobees'}</TooltipContent>
                    </Tooltip>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => deleteJob(selectedJob.id)}
                    >
                      {t('jobs.deleteJob')}
                    </Button>
                  </div>

                  <Separator />

                  {/* HR Contact */}
                  {selectedJob.hr_contact && (
                    <div className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-amber-50 border border-amber-100">
                      <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-amber-500 flex items-center justify-center shrink-0">
                        <Mail className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] sm:text-xs text-amber-600 font-medium">{t('jobs.hrContact')}</p>
                        <p className="text-xs sm:text-sm truncate">{selectedJob.hr_contact}</p>
                      </div>
                    </div>
                  )}

                  {/* Channel Contact */}
                  {selectedJob.channel_contact && (
                    <div className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-blue-50 border border-blue-100">
                      <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-blue-500 flex items-center justify-center shrink-0">
                        <Send className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] sm:text-xs text-blue-600 font-medium">{t('jobs.channelContact')}</p>
                        <p className="text-xs sm:text-sm truncate">{selectedJob.channel_contact}</p>
                      </div>
                    </div>
                  )}

                  {/* Company Link */}
                  {selectedJob.company_link && (
                    <a href={selectedJob.company_link} target="_blank" rel="noopener noreferrer"
                       className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors group">
                      <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-slate-900 flex items-center justify-center shrink-0">
                        <ExternalLink className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[10px] sm:text-xs text-muted-foreground font-medium">{t('jobs.companyWebsite')}</p>
                        <p className="text-xs sm:text-sm truncate group-hover:text-primary transition-colors">{selectedJob.company_link}</p>
                      </div>
                    </a>
                  )}

                  {/* Skills */}
                  {selectedJob.skills && getSkills(selectedJob).length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-2 sm:mb-3">
                        <Code2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                        <h3 className="text-xs sm:text-sm font-semibold">{t('jobs.skills')}</h3>
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
                        <h3 className="text-xs sm:text-sm font-semibold text-blue-800">{t('jobs.roleType')}</h3>
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

                  {/* Job Description */}
                  {selectedJob.jd && (
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                        <h3 className="text-xs sm:text-sm font-semibold">{t('jobs.jd')}</h3>
                      </div>
                      <p className="text-sm text-foreground/70 leading-relaxed break-words">{selectedJob.jd}</p>
                    </div>
                  )}

                  {/* Original Message */}
                  <div className="bg-muted/40 border rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2 sm:mb-3">
                      <MessagesSquare className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-muted-foreground" />
                      <h3 className="text-xs sm:text-sm font-semibold">{t('jobs.originalMessage')}</h3>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5 ml-auto"
                        onClick={async () => {
                          const text = selectedJob?.message?.text?.replace(/<[^>]*>/g, '') || '';
                          const success = await copyToClipboard(text);
                          if (success) {
                            setCopiedMsg(true);
                            setTimeout(() => setCopiedMsg(false), 2000);
                          }
                        }}
                      >
                        {copiedMsg ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5 text-muted-foreground" />}
                      </Button>
                    </div>
                    <div className="text-sm text-foreground/80 leading-relaxed whitespace-pre-wrap break-words prose prose-sm max-w-none"
                         dangerouslySetInnerHTML={{ __html: selectedJob.message?.text || t('jobs.noTextContent') }} />
                    <div className="mt-3 pt-3 border-t flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        {selectedJob.source_type === 'website' ? (
                          <Globe className="w-3 h-3" />
                        ) : (
                          <MessageSquare className="w-3 h-3" />
                        )}
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
                      <p className="text-sm text-foreground/80 leading-relaxed break-words">{selectedJob.notes || t('jobs.noNotes')}</p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                  <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-3">
                    <Briefcase className="w-8 h-8 opacity-40" />
                  </div>
                  <p className="text-sm">{t('jobs.selectJob')}</p>
                </div>
              )}
              </TooltipProvider>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className="shadow-sm">
          <CardContent className="py-24 text-center">
            <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mb-4 mx-auto">
              <Briefcase className="w-8 h-8 opacity-40" />
            </div>
            <p className="font-semibold mb-1">{t('jobs.noJobsFound')}</p>
            <p className="text-sm text-muted-foreground">{t('jobs.noJobsMatch')}</p>
          </CardContent>
        </Card>
      )}


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
