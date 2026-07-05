import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  ArrowLeft,
  ScrollText,
  Sparkles,
  Star,
  Loader2,
  Copy,
  Download,
  CheckCircle2,
  XCircle,
  TrendingUp,
  FileText,
  Wand2,
  Zap,
  RefreshCw,
  Check,
  AlertCircle,
  BarChart3,
  ChevronRight,
} from 'lucide-react';
import api from '@/services/api';
import type { Job } from '@/services/api';
import { useToast, useWebSocketProgress } from '@/components/Layout';
import { copyToClipboard } from '@/utils/clipboard';

const Resume = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const jobId = parseInt(searchParams.get('jobId') || '0') || null;
  const messageId = parseInt(searchParams.get('messageId') || '0') || null;
  const resumeTab = (searchParams.get('tab') as 'generate' | 'enhance' | 'score') || 'generate';

  const [job, setJob] = useState<Job | null>(null);
  const [messageText, setMessageText] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();
  const { resumeGenerating } = useWebSocketProgress();

  const [resumeProvider, setResumeProvider] = useState<{ provider: string; model: string; nvidia_configured: boolean } | null>(null);

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

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        if (jobId) {
          const data = await api.getJob(jobId);
          setJob(data.job || null);
        } else if (messageId) {
          const data = await api.getMessage(messageId);
          if (data.message) setMessageText(data.message.text || '');
        }
      } catch (e: any) {
        showToast('error', e.message || t('common.failedToLoad'));
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [jobId, messageId]);

  useEffect(() => {
    api.getResumeProvider().then(setResumeProvider).catch(() => {});
  }, []);

  const setTab = (tab: 'generate' | 'enhance' | 'score') => {
    const p = new URLSearchParams(searchParams);
    p.set('tab', tab);
    setSearchParams(p, { replace: true });
  };

  const effectiveJobId = jobId;
  const effectiveMessageText = messageText || undefined;

  const handleGenerateResume = async () => {
    setGenerateLoading(true);
    try {
      await api.generateResume(effectiveJobId, (chunk) => setGeneratedText(prev => prev + chunk), effectiveMessageText);
    } catch (e: any) {
      showToast('error', e.message || t('jobs.resumeGenerationFailed'));
    } finally {
      setGenerateLoading(false);
    }
  };

  const handleEnhanceResume = async () => {
    if (!userResumeInput.trim()) { showToast('error', t('jobs.resumePasteFirst')); return; }
    setEnhancedText('');
    setEnhanceLoading(true);
    try {
      await api.enhanceResume(effectiveJobId, userResumeInput, (chunk) => setEnhancedText(prev => prev + chunk), effectiveMessageText);
    } catch (e: any) {
      showToast('error', e.message || t('jobs.resumeEnhancementFailed'));
    } finally {
      setEnhanceLoading(false);
    }
  };

  const handleScoreResume = async () => {
    if (!scoreResumeInput.trim()) { showToast('error', t('jobs.resumePasteFirst')); return; }
    setScoreResult(null);
    setScoreLoading(true);
    try {
      const result = await api.scoreResume(effectiveJobId, scoreResumeInput, effectiveMessageText);
      setScoreResult(result);
    } catch (e: any) {
      showToast('error', e.message || t('jobs.resumeScoringFailed'));
    } finally {
      setScoreLoading(false);
    }
  };

  const downloadText = (text: string, prefix: string) => {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    const title = (job?.title || job?.company || 'message').replace(/\s+/g, '_');
    link.download = `${prefix}_${title}_${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
  };

  const [copiedGen, setCopiedGen] = useState(false);
  const [copiedEnh, setCopiedEnh] = useState(false);

  const scoreLevelMeta = (level: string) => {
    if (level === 'excellent') return { color: 'text-emerald-600', bg: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-700 border-emerald-200' };
    if (level === 'good') return { color: 'text-blue-600', bg: 'bg-blue-500', badge: 'bg-blue-50 text-blue-700 border-blue-200' };
    if (level === 'fair') return { color: 'text-amber-600', bg: 'bg-amber-500', badge: 'bg-amber-50 text-amber-700 border-amber-200' };
    return { color: 'text-red-600', bg: 'bg-red-500', badge: 'bg-red-50 text-red-700 border-red-200' };
  };

  const goBack = () => {
    if (messageId) navigate('/messages');
    else navigate('/jobs');
  };

  const sourceLabel = job
    ? (job.title || job.company || t('jobs.untitledJob'))
    : messageId ? t('jobs.resumeFromMessage') : '';

  const jobDescriptionDisplay = job
    ? [
        job.title && `【${job.title}】${job.company ? `  ·  ${job.company}` : ''}`,
        job.message?.text || job.jd,
      ].filter(Boolean).join('\n\n')
    : messageText;

  const handleCopy = async (text: string, setCopied: (v: boolean) => void) => {
    const success = await copyToClipboard(text);
    if (success) {
      setCopied(true);
      showToast('success', t('jobs.resumeCopied'));
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const PanelHeader = ({ icon, label, accent }: { icon: React.ReactNode; label: string; accent?: string }) => (
    <div className={`flex items-center gap-2.5 px-5 py-3.5 border-b bg-muted/30`}>
      <div className={`flex items-center justify-center w-7 h-7 rounded-md ${accent || 'bg-muted'}`}>
        {icon}
      </div>
      <span className="text-sm font-semibold tracking-tight">{label}</span>
    </div>
  );

  const DescriptionPanel = () => (
    <Card className="flex flex-col overflow-hidden border shadow-sm h-full">
      <PanelHeader
        icon={<FileText className="w-3.5 h-3.5 text-slate-600" />}
        label={t('jobs.resumeJobDescription')}
        accent="bg-slate-100"
      />
      <ScrollArea className="flex-1" style={{ height: 'calc(100vh - 340px)', minHeight: '400px' }}>
        <div className="p-5">
          {jobDescriptionDisplay ? (
            <p className="text-sm text-foreground/80 whitespace-pre-wrap leading-relaxed font-sans">
              {jobDescriptionDisplay}
            </p>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <AlertCircle className="w-8 h-8 mb-3 opacity-40" />
              <p className="text-sm">{t('jobs.noDescription')}</p>
            </div>
          )}
        </div>
      </ScrollArea>
    </Card>
  );

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <Loader2 className="w-7 h-7 animate-spin text-purple-500" />
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!jobId && !messageId) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-purple-50 flex items-center justify-center">
          <ScrollText className="w-8 h-8 text-purple-400" />
        </div>
        <div className="text-center">
          <p className="font-medium">{t('jobs.selectJob')}</p>
          <p className="text-sm text-muted-foreground mt-1">Open a job or message to use AI resume tools</p>
        </div>
        <Button onClick={() => navigate('/jobs')} className="mt-1">
          <ArrowLeft className="w-4 h-4 mr-1.5" />{t('jobs.goBack')}
        </Button>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={400}>
      <div className="flex flex-col gap-0 -mt-1">

        {/* ── Hero Header ── */}
        <div className="relative overflow-hidden rounded-xl mb-5 bg-gradient-to-br from-violet-600 via-purple-600 to-indigo-600 p-5 text-white shadow-lg">
          <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
          <Button
            variant="ghost"
            size="sm"
            onClick={goBack}
            className="text-white/80 hover:text-white hover:bg-white/10 mb-3 -ml-1 h-7 px-2"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />{t('jobs.goBack')}
          </Button>
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <ScrollText className="w-5 h-5" />
                <h1 className="text-xl font-bold tracking-tight">{t('jobs.resumeTitle')}</h1>
              </div>
              {sourceLabel && (
                <div className="flex items-center gap-1.5 text-white/70 text-sm">
                  <ChevronRight className="w-3.5 h-3.5" />
                  <span className="font-medium text-white/90 truncate max-w-xs">{sourceLabel}</span>
                </div>
              )}
            </div>
            {resumeProvider && (
              <div className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border border-white/20 backdrop-blur-sm ${resumeProvider.provider === 'nvidia' ? 'bg-green-500/20 text-green-100' : 'bg-blue-400/20 text-blue-100'}`}>
                <Zap className="w-3 h-3" />
                {resumeProvider.provider === 'nvidia' ? t('jobs.resumeProviderNvidia') : t('jobs.resumeProviderOllama')}
                <span className="opacity-60">·</span>
                <span className="truncate max-w-32">{resumeProvider.model}</span>
              </div>
            )}
          </div>
        </div>

        {/* ── Tabs ── */}
        <Tabs value={resumeTab} onValueChange={(v) => setTab(v as any)} className="flex flex-col gap-4">
          <TabsList className="grid grid-cols-3 w-full sm:w-[460px] h-10">
            <TabsTrigger value="generate" className="gap-1.5 text-xs sm:text-sm">
              <Wand2 className="w-3.5 h-3.5" />{t('jobs.resumeGenerate')}
            </TabsTrigger>
            <TabsTrigger value="enhance" className="gap-1.5 text-xs sm:text-sm">
              <Sparkles className="w-3.5 h-3.5" />{t('jobs.resumeEnhance')}
            </TabsTrigger>
            <TabsTrigger value="score" className="gap-1.5 text-xs sm:text-sm">
              <BarChart3 className="w-3.5 h-3.5" />{t('jobs.resumeScore')}
            </TabsTrigger>
          </TabsList>

          {/* ══════════════════════════════
              GENERATE TAB
          ══════════════════════════════ */}
          <TabsContent value="generate" className="mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <DescriptionPanel />

              {/* Right: Generated Resume */}
              <Card className="flex flex-col overflow-hidden border shadow-sm h-full">
                <PanelHeader
                  icon={<ScrollText className="w-3.5 h-3.5 text-purple-600" />}
                  label={t('jobs.resumeGenerate')}
                  accent="bg-purple-50"
                />
                <ScrollArea className="flex-1" style={{ height: 'calc(100vh - 400px)', minHeight: '360px' }}>
                  <div className="p-5">
                    {generatedText ? (
                      <p className="text-sm text-foreground/85 whitespace-pre-wrap leading-relaxed font-sans">
                        {generatedText}
                        {generateLoading && <span className="inline-block w-0.5 h-4 bg-purple-500 ml-0.5 animate-pulse align-middle" />}
                      </p>
                    ) : generateLoading ? (
                      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
                        <div className="relative">
                          <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                        </div>
                        <p className="text-sm">{t('jobs.generatingResume')}</p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
                        <div className="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center">
                          <ScrollText className="w-7 h-7 text-purple-300" />
                        </div>
                        <p className="text-sm text-center px-4">{t('jobs.resumeEmptyGenerate')}</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
                <div className="border-t bg-muted/20 px-4 py-3 flex items-center gap-2 flex-wrap">
                  <Button
                    size="sm"
                    className="bg-purple-600 hover:bg-purple-700 text-white gap-1.5 h-8"
                    onClick={() => { setGeneratedText(''); void handleGenerateResume(); }}
                    disabled={generateLoading || !!resumeGenerating}
                  >
                    {generateLoading
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />{t('jobs.generatingResume')}</>
                      : generatedText
                      ? <><RefreshCw className="w-3.5 h-3.5" />{t('jobs.regenerateResume')}</>
                      : <><Wand2 className="w-3.5 h-3.5" />{t('jobs.resumeGenerate')}</>}
                  </Button>
                  {generatedText && (
                    <>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => handleCopy(generatedText, setCopiedGen)}>
                            {copiedGen ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                            {t('jobs.resumeCopy')}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Copy to clipboard</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => downloadText(generatedText, 'resume')}>
                            <Download className="w-3.5 h-3.5" />{t('jobs.resumeDownload')}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Download as .txt</TooltipContent>
                      </Tooltip>
                    </>
                  )}
                </div>
              </Card>
            </div>
          </TabsContent>

          {/* ══════════════════════════════
              ENHANCE TAB
          ══════════════════════════════ */}
          <TabsContent value="enhance" className="mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Left: Paste your resume */}
              <Card className="flex flex-col overflow-hidden border shadow-sm">
                <PanelHeader
                  icon={<FileText className="w-3.5 h-3.5 text-slate-600" />}
                  label={t('jobs.resumeCurrentResume')}
                  accent="bg-slate-100"
                />
                <div className="flex-1 flex flex-col p-5 gap-3">
                  <p className="text-xs text-muted-foreground leading-relaxed">{t('jobs.resumeEnhanceDesc')}</p>
                  <Textarea
                    placeholder={t('jobs.resumePasteCurrent')}
                    value={userResumeInput}
                    onChange={(e) => setUserResumeInput(e.target.value)}
                    className="flex-1 text-sm resize-none font-sans leading-relaxed"
                    style={{ minHeight: '320px' }}
                  />
                </div>
                <div className="border-t bg-muted/20 px-4 py-3">
                  <Button
                    size="sm"
                    className="bg-purple-600 hover:bg-purple-700 text-white gap-1.5 h-8"
                    onClick={handleEnhanceResume}
                    disabled={enhanceLoading || !userResumeInput.trim()}
                  >
                    {enhanceLoading
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />{t('jobs.resumeEnhancing')}</>
                      : <><Sparkles className="w-3.5 h-3.5" />{t('jobs.resumeEnhanceBtn')}</>}
                  </Button>
                </div>
              </Card>

              {/* Right: Enhanced result */}
              <Card className="flex flex-col overflow-hidden border shadow-sm">
                <PanelHeader
                  icon={<Sparkles className="w-3.5 h-3.5 text-purple-600" />}
                  label={t('jobs.resumeEnhanced')}
                  accent="bg-purple-50"
                />
                <ScrollArea className="flex-1" style={{ height: 'calc(100vh - 400px)', minHeight: '360px' }}>
                  <div className="p-5">
                    {enhancedText ? (
                      <p className="text-sm text-foreground/85 whitespace-pre-wrap leading-relaxed font-sans">
                        {enhancedText}
                        {enhanceLoading && <span className="inline-block w-0.5 h-4 bg-purple-500 ml-0.5 animate-pulse align-middle" />}
                      </p>
                    ) : enhanceLoading ? (
                      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
                        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
                        <p className="text-sm">{t('jobs.resumeEnhancing')}</p>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
                        <div className="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center">
                          <Sparkles className="w-7 h-7 text-purple-300" />
                        </div>
                        <p className="text-sm text-center px-4">{t('jobs.resumeEmptyEnhance')}</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
                {enhancedText && (
                  <div className="border-t bg-muted/20 px-4 py-3 flex gap-2">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => handleCopy(enhancedText, setCopiedEnh)}>
                          {copiedEnh ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                          {t('jobs.resumeCopy')}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Copy to clipboard</TooltipContent>
                    </Tooltip>
                    <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={() => downloadText(enhancedText, 'enhanced_resume')}>
                      <Download className="w-3.5 h-3.5" />{t('jobs.resumeDownload')}
                    </Button>
                  </div>
                )}
              </Card>
            </div>
          </TabsContent>

          {/* ══════════════════════════════
              SCORE TAB
          ══════════════════════════════ */}
          <TabsContent value="score" className="mt-0">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <DescriptionPanel />

              {/* Right: Resume input + score */}
              <Card className="flex flex-col overflow-hidden border shadow-sm">
                <PanelHeader
                  icon={<BarChart3 className="w-3.5 h-3.5 text-blue-600" />}
                  label={t('jobs.resumeScore')}
                  accent="bg-blue-50"
                />
                <div className="flex flex-col gap-3 p-5 border-b">
                  <p className="text-xs text-muted-foreground leading-relaxed">{t('jobs.resumeScoreDesc')}</p>
                  <Textarea
                    placeholder={t('jobs.resumePasteHere')}
                    value={scoreResumeInput}
                    onChange={(e) => setScoreResumeInput(e.target.value)}
                    className="text-sm resize-none font-sans leading-relaxed min-h-[160px]"
                  />
                  <Button
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700 text-white gap-1.5 self-start h-8"
                    onClick={handleScoreResume}
                    disabled={scoreLoading || !scoreResumeInput.trim()}
                  >
                    {scoreLoading
                      ? <><Loader2 className="w-3.5 h-3.5 animate-spin" />{t('jobs.resumeScoring')}</>
                      : <><TrendingUp className="w-3.5 h-3.5" />{t('jobs.resumeScoreBtn')}</>}
                  </Button>
                </div>

                <ScrollArea className="flex-1" style={{ height: 'calc(100vh - 560px)', minHeight: '240px' }}>
                  <div className="p-5">
                    {scoreLoading && !scoreResult && (
                      <div className="flex flex-col items-center justify-center py-10 gap-3 text-muted-foreground">
                        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
                        <p className="text-sm">{t('jobs.resumeScoring')}</p>
                      </div>
                    )}
                    {!scoreResult && !scoreLoading && (
                      <div className="flex flex-col items-center justify-center py-10 gap-3 text-muted-foreground">
                        <div className="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center">
                          <Star className="w-7 h-7 text-blue-200" />
                        </div>
                        <p className="text-sm text-center px-4">Paste your resume and click Score to analyse the match</p>
                      </div>
                    )}
                    {scoreResult && (() => {
                      const meta = scoreLevelMeta(scoreResult.level);
                      return (
                        <div className="space-y-4">
                          {/* Score banner */}
                          <div className="rounded-xl border bg-gradient-to-r from-slate-50 to-white p-4 flex items-center gap-4">
                            <div className="flex flex-col items-center justify-center w-16 h-16 rounded-xl bg-white border shadow-sm shrink-0">
                              <span className={`text-3xl font-black leading-none ${meta.color}`}>{scoreResult.score}</span>
                              <span className="text-[10px] text-muted-foreground mt-0.5">{t('jobs.resumeOutOf100')}</span>
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-2">
                                <Badge className={`text-xs capitalize border ${meta.badge} font-semibold`}>{scoreResult.level}</Badge>
                              </div>
                              <Progress value={scoreResult.score} className="h-2 mb-2" />
                              <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{scoreResult.summary}</p>
                            </div>
                          </div>

                          {/* Skills grid */}
                          <div className="grid grid-cols-2 gap-3">
                            <div className="rounded-xl border p-3 bg-emerald-50/50">
                              <div className="flex items-center gap-1.5 mb-2.5">
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                                <span className="text-xs font-semibold text-emerald-700">{t('jobs.resumeMatchedSkills')}</span>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {scoreResult.matched_skills.map((s, i) => (
                                  <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0 bg-emerald-50 text-emerald-700 border-emerald-200">{s}</Badge>
                                ))}
                              </div>
                            </div>
                            <div className="rounded-xl border p-3 bg-red-50/50">
                              <div className="flex items-center gap-1.5 mb-2.5">
                                <XCircle className="w-3.5 h-3.5 text-red-500" />
                                <span className="text-xs font-semibold text-red-600">{t('jobs.resumeMissingSkills')}</span>
                              </div>
                              <div className="flex flex-wrap gap-1">
                                {scoreResult.missing_skills.map((s, i) => (
                                  <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0 bg-red-50 text-red-600 border-red-200">{s}</Badge>
                                ))}
                              </div>
                            </div>
                          </div>

                          {/* Strengths */}
                          <div className="rounded-xl border p-3 bg-blue-50/40">
                            <div className="flex items-center gap-1.5 mb-2.5">
                              <Star className="w-3.5 h-3.5 text-blue-600" />
                              <span className="text-xs font-semibold text-blue-700">{t('jobs.resumeStrengths')}</span>
                            </div>
                            <ul className="space-y-1.5">
                              {scoreResult.strengths.map((s, i) => (
                                <li key={i} className="flex items-start gap-1.5 text-xs text-foreground/80">
                                  <CheckCircle2 className="w-3 h-3 text-blue-400 shrink-0 mt-0.5" />{s}
                                </li>
                              ))}
                            </ul>
                          </div>

                          {/* Improvements */}
                          <div className="rounded-xl border p-3 bg-amber-50/40">
                            <div className="flex items-center gap-1.5 mb-2.5">
                              <TrendingUp className="w-3.5 h-3.5 text-amber-600" />
                              <span className="text-xs font-semibold text-amber-700">{t('jobs.resumeImprovements')}</span>
                            </div>
                            <ul className="space-y-1.5">
                              {scoreResult.improvements.map((s, i) => (
                                <li key={i} className="flex items-start gap-1.5 text-xs text-foreground/80">
                                  <ChevronRight className="w-3 h-3 text-amber-400 shrink-0 mt-0.5" />{s}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                </ScrollArea>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  );
};

export default Resume;
