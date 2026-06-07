import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
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

const getSenderName = (dev: Developer) => {
  return dev.message?.sender_username || dev.message?.sender_first_name || 'Unknown';
};

const getInitials = (name: string) => {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
};

const Developers = () => {
  const [developers, setDevelopers] = useState<Developer[]>([]);
  const [selectedDeveloper, setSelectedDeveloper] = useState<Developer | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [total, setTotal] = useState(0);
  const lookingFilter = searchParams.get('looking_for_work');
  const limit = 10;
  const offset = parseInt(searchParams.get('offset') || '0');
  const { showToast } = useToast();

  const filteredDevelopers = developers.filter(dev => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    const senderName = getSenderName(dev).toLowerCase();
    const devName = (dev.name || '').toLowerCase();
    const channelName = (dev.channel?.username || '').toLowerCase();
    const skillsStr = dev.skills ? dev.skills.join(' ').toLowerCase() : '';
    return senderName.includes(query) || devName.includes(query) || channelName.includes(query) || skillsStr.includes(query);
  });

  useEffect(() => {
    loadDevelopers();
  }, [lookingFilter, offset]);

  const loadDevelopers = async () => {
    try {
      const params: any = { limit, offset };
      if (lookingFilter) params.looking_for_work = lookingFilter;
      const data = await api.getDevelopers(params);
      setDevelopers(data.developers);
      setTotal(data.total || 0);
      if (data.developers.length > 0 && !selectedDeveloper) {
        setSelectedDeveloper(data.developers[0]);
      }
    } catch (error) {
      console.error('Failed to load developers:', error);
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

  const applyFilters = () => {
    const looking = (document.getElementById('looking-filter') as HTMLSelectElement)?.value;
    const params = new URLSearchParams();
    if (looking) params.set('looking_for_work', looking);
    setSearchParams(params);
  };

  const clearFilters = () => {
    setSearchParams({});
    setSearchQuery('');
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
        dev.looking_for_work ? 'Yes' : 'No',
        dev.channel?.username || 'Unknown',
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

    showToast('success', `Exported ${developers.length} developers to CSV`);
  };

  const getSkills = (dev: Developer) => {
    return dev.skills || [];
  };

  return (
    <>
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Developers</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {total} developer{total !== 1 ? 's' : ''} found
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <Button variant="outline" size="sm" onClick={exportDevelopers} disabled={developers.length === 0}>
            <Download className="w-4 h-4 mr-1.5" />
            Export CSV
          </Button>
        </div>
      </div>

      {developers.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {/* Left Sidebar - Developer List */}
          <Card className="md:col-span-2">
            <CardHeader className="pb-3">
              <div className="space-y-3">
                {/* Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    placeholder="Search developers..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
                {/* Filters */}
                <div className="flex gap-2">
                  <select
                    id="looking-filter"
                    defaultValue={lookingFilter || ''}
                    onChange={applyFilters}
                    className="flex-1 px-3 py-2 rounded-md border border-gray-200 text-sm bg-white"
                  >
                    <option value="">All Status</option>
                    <option value="true">Looking for Work</option>
                    <option value="false">Not Looking</option>
                  </select>
                  {(lookingFilter || searchQuery) && (
                    <Button variant="ghost" size="sm" onClick={clearFilters}>
                      Clear
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="px-4 pb-4 space-y-1">
                {filteredDevelopers.length === 0 ? (
                  <p className="text-sm text-gray-500 text-center py-8">No developers match your search.</p>
                ) : (
                  filteredDevelopers.map((dev) => {
                    const isSelected = selectedDeveloper?.id === dev.id;
                    const senderName = getSenderName(dev);
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
                            <span className={`font-medium text-sm truncate ${isSelected ? 'text-primary' : ''}`}>
                              {senderName}
                            </span>
                            {dev.looking_for_work && (
                              <Badge variant="default" className="text-[10px] h-5 px-1.5">Looking</Badge>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 truncate">
                            {dev.name || 'Unnamed Developer'}
                          </p>
                          {skills.length > 0 && (
                            <div className="flex gap-1 mt-1.5 flex-wrap">
                              {skills.slice(0, 3).map((skill, idx) => (
                                <span key={idx} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded-md">
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
                            @{dev.channel?.username || 'Unknown'}
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
                </div>
              )}
            </CardContent>
          </Card>

          {/* Right Column - Developer Details */}
          <Card className="md:col-span-3 overflow-visible">
            <CardContent className="pt-4 pb-4 sm:pt-6 sm:pb-6">
                {selectedDeveloper ? (
                  <div className="space-y-6">
                    {/* Header Section */}
                    <div className="flex items-start gap-3 sm:gap-4">
                      <div className="w-11 h-11 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-br from-primary to-primary/70 flex items-center justify-center text-lg sm:text-xl font-bold text-primary-foreground shrink-0">
                        {getInitials(getSenderName(selectedDeveloper))}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap gap-2 sm:gap-2.5 mb-2 max-w-full">
                          <Badge variant={selectedDeveloper.looking_for_work ? 'default' : 'secondary'} className="text-sm px-3 py-1 shrink-0">
                            {selectedDeveloper.looking_for_work ? 'Looking for Work' : 'Not Looking'}
                          </Badge>
                          {selectedDeveloper.confidence && (
                            <Badge variant="outline" className="text-xs sm:text-sm px-2.5 py-0.5 sm:px-3 sm:py-1 shrink-0">
                              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5" />
                              {selectedDeveloper.confidence}
                            </Badge>
                          )}
                          {selectedDeveloper.is_contacted && (
                            <Badge className="bg-green-100 text-green-700 hover:bg-green-100 text-sm px-3 py-1 shrink-0">
                              Contacted
                            </Badge>
                          )}
                        </div>
                        <h2 className="text-lg sm:text-xl font-bold truncate">
                          {selectedDeveloper.name || 'Unnamed Developer'}
                        </h2>
                        <p className="text-xs sm:text-sm text-muted-foreground flex items-center gap-1 mt-0.5 flex-wrap">
                          <Send className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                          <span className="truncate">{getSenderName(selectedDeveloper)}</span>
                          <span className="text-gray-300 hidden sm:inline">|</span>
                          <span className="flex items-center gap-1 sm:hidden w-full mt-0.5">
                            <MessageSquare className="w-3 h-3" />
                            @{selectedDeveloper.channel?.username || 'Unknown'}
                          </span>
                          <span className="hidden sm:flex items-center gap-1">
                            <MessageSquare className="w-3.5 h-3.5" />
                            @{selectedDeveloper.channel?.username || 'Unknown'}
                          </span>
                        </p>
                      </div>
                    </div>

                    <Separator />

                    {/* Contact Links */}
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
                        {selectedDeveloper.portfolio && (
                          <a href={selectedDeveloper.portfolio} target="_blank" rel="noopener noreferrer"
                             className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-emerald-50 hover:bg-emerald-100 transition-colors group">
                            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-emerald-600 flex items-center justify-center shrink-0">
                              <Globe className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-[10px] sm:text-xs text-emerald-600 font-medium">Portfolio</p>
                              <p className="text-xs sm:text-sm text-gray-900 truncate group-hover:text-emerald-700 transition-colors">{selectedDeveloper.portfolio}</p>
                            </div>
                          </a>
                        )}
                        {selectedDeveloper.contact && (
                          <div className="flex items-center gap-2 sm:gap-2.5 p-2.5 sm:p-3 rounded-lg bg-amber-50 border border-amber-100">
                            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-amber-500 flex items-center justify-center shrink-0">
                              <Mail className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-white" />
                            </div>
                            <div className="min-w-0">
                              <p className="text-[10px] sm:text-xs text-amber-600 font-medium">Contact</p>
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
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">Skills</h3>
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
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">Experience</h3>
                        </div>
                        <p className="text-sm text-gray-600 leading-relaxed break-words">{selectedDeveloper.experience}</p>
                      </div>
                    )}

                    {/* Summary */}
                    {selectedDeveloper.summary && (
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <FileText className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-primary" />
                          <h3 className="text-xs sm:text-sm font-semibold text-gray-900">Summary</h3>
                        </div>
                        <p className="text-sm text-gray-600 leading-relaxed break-words">{selectedDeveloper.summary}</p>
                      </div>
                    )}

                    {/* English Translation */}
                    {selectedDeveloper.translated_text && (
                      <div className="bg-blue-50/50 border border-blue-100 rounded-xl p-4">
                        <div className="flex items-center gap-2 mb-2 sm:mb-3">
                          <Languages className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-blue-600" />
                          <h3 className="text-xs sm:text-sm font-semibold text-blue-900">English Translation</h3>
                        </div>
                        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">{selectedDeveloper.translated_text}</p>
                      </div>
                    )}

                    {/* Original Message */}
                    <div className="bg-gray-50 border border-gray-200 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-2 sm:mb-3">
                        <MessagesSquare className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-gray-600" />
                        <h3 className="text-xs sm:text-sm font-semibold text-gray-900">Original Message</h3>
                      </div>
                      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap break-words">{selectedDeveloper.message?.text || '<No text content>'}</p>
                      <div className="mt-3 pt-3 border-t border-gray-200 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <User className="w-3 h-3" />
                          {selectedDeveloper.message?.sender_username || selectedDeveloper.message?.sender_first_name || 'Unknown'}
                        </span>
                        <span className="flex items-center gap-1">
                          <MessageSquare className="w-3 h-3" />
                          @{selectedDeveloper.channel?.username || 'Unknown'}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {selectedDeveloper.message?.date ? new Date(selectedDeveloper.message.date).toLocaleString() : 'Unknown'}
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-64 text-gray-400">
                    <User className="w-12 h-12 mb-3 opacity-50" />
                    <p className="text-sm">Select a developer to view details</p>
                  </div>
                )}
              </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <CardContent className="pt-12 pb-12 text-center">
            <User className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p className="text-gray-500 mb-1 font-medium">No developers found</p>
            <p className="text-sm text-gray-400 mb-4">Try searching some channels first to find developer profiles.</p>
            <Button asChild variant="outline">
              <a href="/channels">Go to Channels</a>
            </Button>
          </CardContent>
        </Card>
      )}
    </>
  );
};

export default Developers;
