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
import {
  Globe,
  Mail,
  MessageSquare,
  Calendar,
  User,
  CheckCircle2,
  Search,
  Download,
  Code2,
  Briefcase,
  FileText,
  Languages,
  MessagesSquare,
  Send,
  ExternalLink
} from 'lucide-react';
import api from '@/services/api';
import type { Developer } from '@/services/api';
import { useToast } from '@/components/Layout';

const getSenderName = (dev: Developer, fallback = 'Unknown') => {
  return dev.message?.sender_username || dev.message?.sender_first_name || fallback;
};

const getInitials = (name: string) => {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

const Developers = () => {
  const { t } = useTranslation();
  const [developers, setDevelopers] = useState<Developer[]>([]);
  const [selectedDeveloper, setSelectedDeveloper] = useState<Developer | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [total, setTotal] = useState(0);
  const [developerNotes, setDeveloperNotes] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [developerToDelete, setDeveloperToDelete] = useState<number | null>(null);
  const lookingFilter = searchParams.get('looking_for_work');
  const contactedFilter = searchParams.get('is_contacted');
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');
  const developerIdParam = searchParams.get('developerId');
  const { showToast } = useToast();

  useEffect(() => {
    loadDevelopers();
  }, [lookingFilter, contactedFilter, offset, searchQuery]);

  useEffect(() => {
    if (developerIdParam && developers.length > 0) {
      const devToSelect = developers.find(d => d.id === parseInt(developerIdParam));
      if (devToSelect) {
        setSelectedDeveloper(devToSelect);
        // Clear the param after selecting
        setSearchParams({});
      }
    }
  }, [developerIdParam, developers]);

  const loadDevelopers = async () => {
    try {
      const params: any = { limit, offset };
      if (lookingFilter) params.looking_for_work = lookingFilter;
      if (contactedFilter) params.is_contacted = contactedFilter;
      if (searchQuery) params.search = searchQuery;
      const data = await api.getDevelopers(params);
      setDevelopers(data.developers);
      setTotal(data.total || 0);
      if (data.developers.length > 0 && !selectedDeveloper) {
        setSelectedDeveloper(data.developers[0]);
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToLoad')} ${t('developers.title')}`;
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

  const applyFilters = () => {
    const looking = (document.getElementById('looking-filter') as HTMLSelectElement)?.value;
    const contacted = (document.getElementById('contacted-filter') as HTMLSelectElement)?.value;
    const params = new URLSearchParams(searchParams);
    params.delete('offset');
    if (looking) params.set('looking_for_work', looking);
    else params.delete('looking_for_work');
    if (contacted) params.set('is_contacted', contacted);
    else params.delete('is_contacted');
    setSearchParams(params);
  };

  const clearFilters = () => {
    setSearchParams({});
    setSearchQuery('');
    setSearchInput('');
  };

  const toggleContacted = async (id: number) => {
    const developer = developers.find(d => d.id === id);
    if (developer?.is_contacted) {
      showToast('warning', t('developers.alreadyContacted'));
      return;
    }
    // Optimistic update
    setDevelopers(prevDevs => prevDevs.map(d => d.id === id ? { ...d, is_contacted: true } : d));
    if (selectedDeveloper?.id === id) {
      setSelectedDeveloper(prev => prev ? { ...prev, is_contacted: true } : null);
    }
    try {
      const result = await api.toggleDeveloperContacted(id, developerNotes);
      if (result.developer) {
        // Update with the returned developer data which includes notes
        const updatedDeveloper = result.developer;
        setDevelopers(prevDevs => prevDevs.map(d => d.id === id ? updatedDeveloper : d));
        if (selectedDeveloper?.id === id) {
          setSelectedDeveloper(updatedDeveloper);
        }
      } else {
        loadDevelopers();
      }
      setDeveloperNotes('');
      showToast('success', t('developers.markedAsContacted'));
    } catch (e: any) {
      let errorMessage = `${t('common.failedToToggle')} ${t('developers.contactStatus')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
      // Revert on error
      loadDevelopers();
    }
  };

  const deleteDeveloper = async (id: number) => {
    setDeveloperToDelete(id);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteDeveloper = async () => {
    if (!developerToDelete) return;
    try {
      await api.deleteDeveloper(developerToDelete);
      setDevelopers(prevDevs => prevDevs.filter(d => d.id !== developerToDelete));
      if (selectedDeveloper?.id === developerToDelete) {
        setSelectedDeveloper(developers.find(d => d.id !== developerToDelete) || null);
      }
      showToast('success', t('developers.deletedSuccessfully'));
      setDeleteDialogOpen(false);
      setDeveloperToDelete(null);
    } catch (e: any) {
      let errorMessage = `${t('common.failedToDelete')} ${t('developers.title')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    }
  };

  const exportDevelopers = () => {
    const headers = ['Name', 'Skills', 'Experience', 'GitHub', 'LinkedIn', 'Portfolio', 'Contact', 'Looking for Work', 'Channel', 'Posted Date'];
    const rows = developers.map(dev => {
      return [
        dev.name || '',
        dev.skills ? dev.skills.join(', ') : '',
        dev.experience || '',
        dev.github || '',
        dev.linkedin || '',
        dev.portfolio || '',
        dev.contact || '',
        dev.looking_for_work ? t('common.yes') : t('common.no'),
        dev.channel?.username || t('common.unknown'),
        dev.message.date ? new Date(dev.message.date).toLocaleDateString() : ''
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
    link.setAttribute('download', `developers_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('success', t('developers.exportedDevelopers', { count: developers.length }));
  };

  const getSkills = (dev: Developer) => {
    return dev.skills || [];
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('developers.title')}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total} developer{total !== 1 ? 's' : ''} found
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" onClick={exportDevelopers} disabled={developers.length === 0}>
            <Download className="w-4 h-4 mr-1.5" />
            {t('common.exportCsv')}
          </Button>
        </div>
      </div>

      {(developers.length > 0 || searchQuery) ? (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* Left Sidebar - Developer List */}
          <Card className="lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="space-y-3">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    placeholder={t('developers.searchPlaceholder')}
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') { const p = new URLSearchParams(searchParams); p.delete('offset'); setSearchParams(p); setSearchQuery(searchInput); } }}
                    className="pl-9"
                  />
                </div>
                {/* Filters */}
                <div className="flex flex-col sm:flex-row gap-2">
                  <select
                    id="looking-filter"
                    defaultValue={lookingFilter || ''}
                    onChange={applyFilters}
                    className="flex-1 px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="">{t('common.allStatus')}</option>
                    <option value="true">{t('developers.lookingForWork')}</option>
                    <option value="false">{t('developers.notLooking')}</option>
                  </select>
                  <select
                    id="contacted-filter"
                    defaultValue={contactedFilter || ''}
                    onChange={applyFilters}
                    className="flex-1 px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="">{t('common.allContacted')}</option>
                    <option value="true">{t('developers.contacted')}</option>
                    <option value="false">{t('developers.notContacted')}</option>
                  </select>
                  {(lookingFilter || contactedFilter || searchQuery) && (
                    <Button variant="ghost" size="sm" onClick={clearFilters}>
                      {t('common.clear')}
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-4 pb-4 space-y-1">
                {developers.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-8">{t('developers.noDevsMatch')}</p>
                ) : (
                  developers.map((dev) => {
                    const isSelected = selectedDeveloper?.id === dev.id;
                    const senderName = getSenderName(dev, t('common.unknown'));
                    const skills = getSkills(dev);
                    return (
                      <div
                        key={dev.id}
                        onClick={() => setSelectedDeveloper(dev)}
                        className={`flex items-start gap-3 p-3 rounded-xl cursor-pointer transition-all ${
                          isSelected
                            ? 'bg-primary/5 border border-primary/20 shadow-sm'
                            : 'hover:bg-gray-50 border border-transparent'
                        }`}
                      >
                        {/* Avatar */}
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold shrink-0 ${
                          isSelected
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-gray-200 text-gray-700'
                        }`}>
                          {getInitials(senderName)}
                        </div>
                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className={`font-medium text-base truncate ${isSelected ? 'text-primary' : ''}`}>
                              {senderName}
                            </span>
                            {dev.is_contacted && (
                              <Badge variant="default" className="text-xs h-5 px-1.5">{t('developers.contacted')}</Badge>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 truncate">
                            {dev.name || t('developers.unnamedDeveloper')}
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
                            @{dev.channel?.username || t('common.unknown')}
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              {/* Pagination */}
              {developers.length > 0 && (
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

          {/* Right Column - Developer Details */}
          <Card className="lg:col-span-3 overflow-visible">
            <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
                {selectedDeveloper ? (
                  <div className="space-y-6">
                    {/* Header Section */}
                    <div className="flex items-start gap-3 sm:gap-4">
                      <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-lg sm:text-xl font-bold text-primary-foreground shrink-0">
                        {getInitials(getSenderName(selectedDeveloper, t('common.unknown')))}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap gap-2 sm:gap-2.5 mb-2 max-w-full">
                          <Badge variant={selectedDeveloper.looking_for_work ? 'default' : 'secondary'} className="text-sm px-3 py-1 shrink-0">
                            {selectedDeveloper.looking_for_work ? t('developers.lookingForWork') : t('developers.notLooking')}
                          </Badge>
                          {selectedDeveloper.confidence && (
                            <Badge variant="outline" className="text-xs sm:text-sm px-2.5 py-0.5 sm:px-3 sm:py-1 shrink-0">
                              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                              {selectedDeveloper.confidence}
                            </Badge>
                          )}
                          {selectedDeveloper.is_contacted && (
                            <Badge className="bg-green-100 text-green-700 hover:bg-green-100 text-sm px-3 py-1 shrink-0">
                              {t('developers.contacted')}
                            </Badge>
                          )}
                        </div>
                        <h2 className="text-lg sm:text-xl font-bold truncate">
                          {selectedDeveloper.name || t('developers.unnamedDeveloper')}
                        </h2>
                        <p className="text-xs sm:text-sm text-muted-foreground flex items-center gap-1 mt-0.5 flex-wrap">
                          <Send className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                          <span className="truncate">{getSenderName(selectedDeveloper, t('common.unknown'))}</span>
                          <span className="text-gray-300 hidden sm:inline">|</span>
                          <span className="flex items-center gap-1 sm:hidden w-full mt-0.5">
                            <MessageSquare className="w-3 h-3" />
                            @{selectedDeveloper.channel?.username || t('common.unknown')}
                          </span>
                          <span className="hidden sm:flex items-center gap-1">
                            <MessageSquare className="w-3.5 h-3.5" />
                            @{selectedDeveloper.channel?.username || t('common.unknown')}
                          </span>
                        </p>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 pt-2">
                      {!selectedDeveloper.is_contacted && (
                        <Input
                          placeholder={t('developers.addNotes')}
                          value={developerNotes}
                          onChange={(e) => setDeveloperNotes(e.target.value)}
                          className="flex-1"
                        />
                      )}
                      <Button
                        size="sm"
                        variant={selectedDeveloper.is_contacted ? 'default' : 'outline'}
                        onClick={() => toggleContacted(selectedDeveloper.id)}
                      >
                        {selectedDeveloper.is_contacted ? t('developers.contacted') + ' ✓' : t('developers.markContacted')}
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => deleteDeveloper(selectedDeveloper.id)}
                      >
                        {t('developers.deleteDeveloper')}
                      </Button>
                    </div>

                    <Separator />

                    {/* Contact Links — backend normalizes: github/linkedin/contact=string, portfolio=array|string */}
                    {(selectedDeveloper.github || selectedDeveloper.linkedin || selectedDeveloper.portfolio || selectedDeveloper.contact) && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {selectedDeveloper.github && (
                          <a href={selectedDeveloper.github} target="_blank" rel="noopener noreferrer"
                             className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors group">
                            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-gray-900 flex items-center justify-center shrink-0">
                              <ExternalLink className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-[10px] sm:text-xs text-gray-500 font-medium">GitHub</p>
                              <p className="text-xs sm:text-sm text-gray-900 truncate group-hover:text-primary transition-colors">{selectedDeveloper.github}</p>
                            </div>
                          </a>
                        )}
                        {selectedDeveloper.linkedin && (
                          <a href={selectedDeveloper.linkedin} target="_blank" rel="noopener noreferrer"
                             className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-blue-50 hover:bg-blue-100 transition-colors group">
                            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-[#0A66C2] flex items-center justify-center shrink-0">
                              <ExternalLink className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-[10px] sm:text-xs text-blue-600 font-medium">LinkedIn</p>
                              <p className="text-xs sm:text-sm text-gray-900 truncate group-hover:text-blue-700 transition-colors">{selectedDeveloper.linkedin}</p>
                            </div>
                          </a>
                        )}
                        {Array.isArray(selectedDeveloper.portfolio)
                          ? selectedDeveloper.portfolio.map((item: any, idx: number) => {
                              const type = item?.type || 'Portfolio';
                              const value = item?.value;
                              if (!value) return null;
                              const getStyle = (t: string) => {
                                switch (t.toLowerCase()) {
                                  case 'github': return { icon: '📦', bg: 'bg-gray-900', text: 'text-gray-600', hover: 'hover:bg-gray-100' };
                                  case 'demo':   return { icon: '🎮', bg: 'bg-purple-600', text: 'text-purple-600', hover: 'hover:bg-purple-100' };
                                  case 'video':  return { icon: '🎬', bg: 'bg-red-600', text: 'text-red-600', hover: 'hover:bg-red-100' };
                                  default:       return { icon: '🌐', bg: 'bg-emerald-600', text: 'text-emerald-600', hover: 'hover:bg-emerald-100' };
                                }
                              };
                              const { icon, bg, text, hover } = getStyle(type);
                              return (
                                <a key={idx} href={value} target="_blank" rel="noopener noreferrer"
                                   className={`flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-gray-50 ${hover} transition-colors group`}>
                                  <div className={`w-8 h-8 sm:w-9 sm:h-9 rounded-lg ${bg} flex items-center justify-center shrink-0 text-lg`}>{icon}</div>
                                  <div className="min-w-0">
                                    <p className={`text-[10px] sm:text-xs ${text} font-medium`}>{type}</p>
                                    <p className="text-xs sm:text-sm text-gray-900 truncate group-hover:text-gray-700 transition-colors">{value}</p>
                                  </div>
                                </a>
                              );
                            })
                          : selectedDeveloper.portfolio && (
                              <a href={selectedDeveloper.portfolio} target="_blank" rel="noopener noreferrer"
                                 className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-emerald-50 hover:bg-emerald-100 transition-colors group">
                                <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-emerald-600 flex items-center justify-center shrink-0">
                                  <Globe className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                                </div>
                                <div className="min-w-0">
                                  <p className="text-[10px] sm:text-xs text-emerald-600 font-medium">{t('developers.portfolio')}</p>
                                  <p className="text-xs sm:text-sm text-gray-900 truncate group-hover:text-emerald-700 transition-colors">{selectedDeveloper.portfolio}</p>
                                </div>
                              </a>
                            )
                        }
                        {selectedDeveloper.contact && (
                          <div className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-amber-50 border border-amber-100">
                            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-amber-500 flex items-center justify-center shrink-0">
                              <Mail className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-[10px] sm:text-xs text-amber-600 font-medium">{t('jobs.contact')}</p>
                              <p className="text-xs sm:text-sm text-gray-900 truncate">{selectedDeveloper.contact}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Skills */}
                    {selectedDeveloper.skills && getSkills(selectedDeveloper).length > 0 && (
                      <div>
                        <div className="flex items-center gap-2 mb-2 sm:mb-3">
                          <Code2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('developers.skills')}</h3>
                        </div>
                        <div className="flex flex-wrap gap-2.5">
                          {getSkills(selectedDeveloper).map((skill, idx) => (
                            <Badge key={idx} variant="secondary" className="px-4 py-1.5 text-sm font-medium bg-primary/10 text-primary hover:bg-primary/20">
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Experience */}
                    {selectedDeveloper.experience && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Briefcase className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('developers.experience')}</h3>
                        </div>
                        <p className="text-sm text-gray-600 leading-relaxed break-words">{selectedDeveloper.experience}</p>
                      </div>
                    )}

                    {/* Summary */}
                    {selectedDeveloper.summary && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('developers.summary')}</h3>
                        </div>
                        <p className="text-sm text-gray-600 leading-relaxed break-words">{selectedDeveloper.summary}</p>
                      </div>
                    )}

                    {/* English Translation */}
                    {selectedDeveloper.translated_text && (
                      <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2 sm:mb-3">
                          <Languages className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-blue-600" />
                          <h3 className="text-xs sm:text-sm font-semibold text-blue-900">{t('developers.englishTranslation')}</h3>
                        </div>
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">{selectedDeveloper.translated_text}</p>
                      </div>
                    )}

                    {/* Original Message */}
                    {selectedDeveloper.message && (
                      <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2 sm:mb-3">
                          <MessagesSquare className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-gray-600" />
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">{t('developers.originalMessage')}</h3>
                        </div>
                        <div className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words prose prose-sm max-w-none"
                             dangerouslySetInnerHTML={{ __html: selectedDeveloper.message.text || t('developers.noTextContent') }} />
                        <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {selectedDeveloper.message.sender_username || selectedDeveloper.message.sender_first_name || t('common.unknown')}
                          </span>
                          <span className="flex items-center gap-1">
                            <MessageSquare className="w-3 h-3" />
                            @{selectedDeveloper.channel?.username || t('common.unknown')}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {selectedDeveloper.message.date ? new Date(selectedDeveloper.message.date).toLocaleString() : t('common.unknown')}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Notes */}
                    {selectedDeveloper.notes && (
                      <div className="bg-yellow-50/50 border border-yellow-100 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-yellow-600" />
                          <h3 className="text-xs sm:text-sm font-semibold text-yellow-900">{t('developers.notes')}</h3>
                        </div>
                        <p className="text-sm text-gray-700 leading-relaxed break-words">{selectedDeveloper.notes}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <User className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">{t('developers.selectDeveloper')}</p>
                  </div>
                )}
              </CardContent>
          </Card>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Left Column - Developers List */}
          <Card className="md:col-span-1">
            <CardHeader>
              <CardTitle className="text-lg">{t('developers.title')}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-4 pb-4 space-y-1">
                <p className="text-sm text-gray-500 text-center py-8">{t('developers.noDevsFound')}</p>
              </div>
            </CardContent>
          </Card>

          {/* Right Column - Developer Details */}
          <Card className="md:col-span-3">
            <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
              <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                <User className="w-12 h-12 mb-3 opacity-50" />
                <p className="text-sm">{t('developers.selectDeveloper')}</p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('developers.deleteConfirm')}</DialogTitle>
            <DialogDescription>
              {t('developers.deleteWarning')}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button variant="destructive" onClick={confirmDeleteDeveloper}>
              {t('common.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default Developers;
