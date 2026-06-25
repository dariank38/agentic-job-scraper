import { useEffect, useState } from 'react';
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
      showToast('error', e.message || 'Failed to load resumes');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResumes();
  }, [filter]);

  const handleDelete = async (resumeId: number) => {
    if (!confirm('Are you sure you want to delete this resume?')) return;
    setDeleting(resumeId);
    try {
      await api.deleteResume(resumeId);
      showToast('success', 'Resume deleted');
      loadResumes();
      if (selectedResume?.id === resumeId) setSelectedResume(null);
    } catch (e: any) {
      showToast('error', e.message || 'Failed to delete resume');
    } finally {
      setDeleting(null);
    }
  };

  const handleCopy = (content: string) => {
    copyToClipboard(content);
    showToast('success', 'Copied to clipboard');
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
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => window.history.back()}
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                Resume History
              </h1>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                View and manage your generated resumes
              </p>
            </div>
          </div>
        </div>

        {/* Filter */}
        <div className="flex gap-2 mb-6">
          <Button
            variant={filter === 'all' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('all')}
          >
            <Filter className="w-4 h-4 mr-2" />
            All
          </Button>
          <Button
            variant={filter === 'generate' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('generate')}
          >
            <Sparkles className="w-4 h-4 mr-2" />
            Generate
          </Button>
          <Button
            variant={filter === 'enhance' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('enhance')}
          >
            <TrendingUp className="w-4 h-4 mr-2" />
            Enhance
          </Button>
          <Button
            variant={filter === 'score' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter('score')}
          >
            <ScrollText className="w-4 h-4 mr-2" />
            Score
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
              Back to list
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
                    Copy
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
                      Score Result
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
                        Matched Skills
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
                        Missing Skills
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
              No resumes found
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Generate your first resume to see it here
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
    </div>
  );
};

export default ResumeHistory;
