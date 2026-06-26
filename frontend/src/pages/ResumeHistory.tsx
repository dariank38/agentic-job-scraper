import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  ArrowLeft,
  ScrollText,
  Trash2,
  Eye,
  Calendar,
  Building2,
  Sparkles,
  TrendingUp,
  Loader2,
  Filter,
} from 'lucide-react';
import api from '@/services/api';
import { useToast } from '@/components/Layout';
import { copyToClipboard } from '@/utils/clipboard';

interface Resume {
  id: number;
  job_id: number | null;
  job_title: string;
  job_company: string | null;
  resume_type: 'generate' | 'enhance' | 'score';
  content: string;
  score_result: {
    score: number;
    level: string;
    summary: string;
    matched_skills: string[];
    missing_skills: string[];
    strengths: string[];
    improvements: string[];
  } | null;
  created_at: string;
}

const ResumeHistory = () => {
  const { t } = useTranslation();
  const { showToast } = useToast();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'generate' | 'enhance' | 'score'>('all');
  const [selectedResume, setSelectedResume] = useState<Resume | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  const loadResumes = async () => {
    setLoading(true);
    try {
      const params = filter === 'all' ? undefined : { resume_type: filter };
      const data = await api.listResumes(params);
      setResumes(data.resumes);
    } catch (e: any) {
      showToast('error', e.message || t('resumeHistory.failedToLoad'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResumes();
  }, [filter]);

  const handleDelete = async (resumeId: number) => {
    if (!confirm(t('resumeHistory.confirmDelete'))) return;
    setDeleting(resumeId);
    try {
      await api.deleteResume(resumeId);
      showToast('success', t('resumeHistory.deleted'));
      loadResumes();
      if (selectedResume?.id === resumeId) setSelectedResume(null);
    } catch (e: any) {
      showToast('error', e.message || t('resumeHistory.deleteFailed'));
    } finally {
      setDeleting(null);
    }
  };

  const handleCopy = (content: string) => {
    copyToClipboard(content);
    showToast('success', t('resumeHistory.copied'));
  };

  const getResumeTypeIcon = (type: string) => {
    switch (type) {
      case 'generate':
        return <Sparkles className="w-4 h-4" />;
      case 'enhance':
        return <TrendingUp className="w-4 h-4" />;
      case 'score':
        return <ScrollText className="w-4 h-4" />;
      default:
        return <ScrollText className="w-4 h-4" />;
    }
  };

  const getResumeTypeColor = (type: string) => {
    switch (type) {
      case 'generate':
        return 'bg-blue-500/10 text-blue-600 border-blue-500/20';
      case 'enhance':
        return 'bg-green-500/10 text-green-600 border-green-500/20';
      case 'score':
        return 'bg-purple-500/10 text-purple-600 border-purple-500/20';
      default:
        return 'bg-gray-500/10 text-gray-600 border-gray-500/20';
    }
  };

  const getScoreColor = (level: string) => {
    switch (level) {
      case 'excellent':
        return 'text-green-600';
      case 'good':
        return 'text-blue-600';
      case 'fair':
        return 'text-yellow-600';
      case 'poor':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="flex flex-col gap-0 -mt-1">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl mb-5 bg-gradient-to-br from-violet-600 via-purple-600 to-indigo-600 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <ScrollText className="w-5 h-5" />
              <h1 className="text-xl font-bold tracking-tight">{t('resumeHistory.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{t('resumeHistory.subtitle')}</p>
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        <Button
          variant={filter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('all')}
        >
          <Filter className="w-4 h-4 mr-2" />
          {t('resumeHistory.filterAll')}
        </Button>
        <Button
          variant={filter === 'generate' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('generate')}
        >
          <Sparkles className="w-4 h-4 mr-2" />
          {t('resumeHistory.filterGenerate')}
        </Button>
        <Button
          variant={filter === 'enhance' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('enhance')}
        >
          <TrendingUp className="w-4 h-4 mr-2" />
          {t('resumeHistory.filterEnhance')}
        </Button>
        <Button
          variant={filter === 'score' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('score')}
        >
          <ScrollText className="w-4 h-4 mr-2" />
          {t('resumeHistory.filterScore')}
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
        </div>
      ) : selectedResume ? (
        <div className="space-y-4">
          <Button
            variant="outline"
            onClick={() => setSelectedResume(null)}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('resumeHistory.backToList')}
          </Button>

          <Card className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  {getResumeTypeIcon(selectedResume.resume_type)}
                  <Badge className={getResumeTypeColor(selectedResume.resume_type)}>
                    {selectedResume.resume_type}
                  </Badge>
                  {selectedResume.score_result && (
                    <Badge className="bg-purple-500/10 text-purple-600 border-purple-500/20">
                      Score: {selectedResume.score_result.score}/100
                    </Badge>
                  )}
                </div>
                <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">
                  {selectedResume.job_title}
                </h2>
                {selectedResume.job_company && (
                  <p className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-1">
                    <Building2 className="w-4 h-4" />
                    {selectedResume.job_company}
                  </p>
                )}
                <p className="text-xs text-slate-500 dark:text-slate-500 mt-1 flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(selectedResume.created_at)}
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCopy(selectedResume.content)}
                >
                  {t('resumeHistory.copy')}
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => handleDelete(selectedResume.id)}
                  disabled={deleting === selectedResume.id}
                >
                  {deleting === selectedResume.id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Trash2 className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>

            {selectedResume.score_result && (
              <div className="mb-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                <div className="flex items-center gap-2 mb-2">
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100">
                    {t('resumeHistory.scoreResult')}
                  </h3>
                  <Badge className={getScoreColor(selectedResume.score_result.level)}>
                    {selectedResume.score_result.level}
                  </Badge>
                </div>
                <p className="text-sm text-slate-700 dark:text-slate-300 mb-3">
                  {selectedResume.score_result.summary}
                </p>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="font-medium text-slate-900 dark:text-slate-100 mb-1">
                      {t('resumeHistory.matchedSkills')}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {selectedResume.score_result.matched_skills.map((skill, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="font-medium text-slate-900 dark:text-slate-100 mb-1">
                      {t('resumeHistory.missingSkills')}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {selectedResume.score_result.missing_skills.map((skill, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <ScrollArea className="h-[600px] w-full rounded-md border p-4">
              <pre className="whitespace-pre-wrap text-sm text-slate-700 dark:text-slate-300 font-mono">
                {selectedResume.content}
              </pre>
            </ScrollArea>
          </Card>
        </div>
      ) : resumes.length === 0 ? (
        <Card className="p-12 text-center">
          <ScrollText className="w-16 h-16 mx-auto mb-4 text-slate-400" />
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 mb-2">
            {t('resumeHistory.noResumes')}
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            {t('resumeHistory.noResumesDesc')}
          </p>
        </Card>
      ) : (
        <div className="grid gap-4">
          {resumes.map((resume) => (
            <Card key={resume.id} className="p-4 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    {getResumeTypeIcon(resume.resume_type)}
                    <Badge className={getResumeTypeColor(resume.resume_type)}>
                      {resume.resume_type}
                    </Badge>
                    {resume.score_result && (
                      <Badge className="bg-purple-500/10 text-purple-600 border-purple-500/20">
                        Score: {resume.score_result.score}/100
                      </Badge>
                    )}
                  </div>
                  <h3 className="font-semibold text-slate-900 dark:text-slate-100 mb-1">
                    {resume.job_title}
                  </h3>
                  {resume.job_company && (
                    <p className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-1">
                      <Building2 className="w-4 h-4" />
                      {resume.job_company}
                    </p>
                  )}
                  <p className="text-xs text-slate-500 dark:text-slate-500 mt-1 flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    {formatDate(resume.created_at)}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedResume(resume)}
                  >
                    <Eye className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(resume.id)}
                    disabled={deleting === resume.id}
                  >
                    {deleting === resume.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4" />
                    )}
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ResumeHistory;
