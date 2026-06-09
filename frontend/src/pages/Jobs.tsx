import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
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
  ExternalLink
} from 'lucide-react';
import api from '@/services/api';
import type { Job } from '@/services/api';
import { useToast } from '@/components/Layout';

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
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');
  const { showToast } = useToast();

  useEffect(() => {
    loadJobs();
  }, [offset, searchQuery]);

  const loadJobs = async () => {
    try {
      const params: any = { limit, offset };
      if (searchQuery) params.search = searchQuery;
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

  const clearFilters = () => {
    setSearchParams({});
    setSearchQuery('');
    setSearchInput('');
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
      let errorMessage = `${t('common.failedToToggle')} ${t('jobs.status')}`;
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

  const exportJobs = () => {
    const headers = ['Title', 'Company', 'Location', 'Role Type', 'Skills', 'Contact', 'Remote', 'Applied', 'Channel', 'Posted Date'];
    const rows = jobs.map(job => {
      const skillsStr = Array.isArray(job.skills) ? job.skills.join(', ') : '';
      return [
        job.title || '',
        job.company || '',
        job.location || '',
        job.role_type || '',
        skillsStr,
        job.contact || '',
        job.is_remote ? 'Yes' : 'No',
        job.is_applied ? 'Yes' : 'No',
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

  const getSkills = (job: Job) => {
    return job.skills || [];
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('jobs.title')}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total} job{total !== 1 ? 's' : ''} found
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
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {/* Left Sidebar - Job List */}
          <Card className="md:col-span-2">
            <CardHeader className="pb-3">
              <div className="space-y-3">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    placeholder={t('jobs.searchPlaceholder')}
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { setSearchParams({}); setSearchQuery(searchInput); } }}
                    className="pl-9"
                  />
                </div>
                {searchQuery && (
                  <Button variant="ghost" size="sm" onClick={clearFilters}>
                    {t('common.clear')}
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
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
                        {/* Avatar */}
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-semibold shrink-0 ${
                          isSelected
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-gray-200 text-gray-700'
                        }`}>
                          {getInitials(job.company || job.title || 'Job')}
                        </div>
                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className={`font-medium text-base truncate ${isSelected ? 'text-primary' : ''}`}>
                              {job.title || t('jobs.untitledJob')}
                            </span>
                            {job.is_applied && (
                              <Badge variant="default" className="text-xs h-5 px-1.5">{t('jobs.applied')}</Badge>
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
                          <div className="flex items-center gap-1 mt-1 text-[10px] text-gray-400">
                            <MessageSquare className="w-3 h-3" />
                            {job.channel_name || job.channel?.username || t('common.unknown')}
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
                  <div className="flex items-center justify-between pt-3 border-t">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handlePrevious}
                      disabled={offset === 0}
                    >
                      {t('common.previous')}
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      {t('common.page')} {Math.floor(offset / limit) + 1} / {Math.ceil(total / limit)} ({offset + 1}-{Math.min(offset + limit, total)} / {total})
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleNext}
                      disabled={offset + limit >= total}
                    >
                      {t('common.next')}
                    </Button>
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
                      {getInitials(selectedJob.company || selectedJob.title || 'Job')}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap gap-2 sm:gap-2.5 mb-2 max-w-full">
                        <Badge variant={selectedJob.is_applied ? 'default' : 'secondary'} className="text-sm px-3 py-1 shrink-0">
                          {selectedJob.is_applied ? t('jobs.applied') : t('jobs.notApplied')}
                        </Badge>
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
                        {selectedJob.title || t('jobs.untitledJob')}
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
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <Briefcase className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                        <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('jobs.roleType')}</h3>
                      </div>
                      <p className="text-sm text-gray-600 leading-relaxed break-words">{selectedJob.role_type}</p>
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
                    </div>
                    <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">{selectedJob.message?.text || t('jobs.noTextContent')}</p>
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

                  {/* Action Buttons */}
                  <div className="flex gap-2 pt-2">
                    {!selectedJob.is_applied && (
                      <Input
                        placeholder={t('jobs.addNotes')}
                        value={jobNotes}
                        onChange={(e) => setJobNotes(e.target.value)}
                        className="flex-1"
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
                  </div>

                  {/* Notes */}
                  {selectedJob.notes && (
                    <div className="bg-yellow-50/50 border border-yellow-100 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-yellow-600" />
                        <h3 className="text-xs sm:text-sm font-semibold text-yellow-900">{t('jobs.notes')}</h3>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed break-words">{selectedJob.notes}</p>
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
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <Briefcase className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-gray-500 mb-1 font-medium">{t('jobs.noJobsFound')}</p>
            <p className="text-sm text-gray-400 mb-4">{t('jobs.goToChannelsHint')}</p>
            <Button asChild variant="outline">
              <a href="/channels">{t('jobs.goToChannels')}</a>
            </Button>
          </CardContent>
        </Card>
      )}

    </>
  );
};

export default Jobs;
