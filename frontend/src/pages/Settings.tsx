import { useState, useEffect } from 'react';
import { Settings2, Cpu, RefreshCw, CheckCircle, AlertCircle, Zap, Bot, ExternalLink, Server, Pencil, X, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/components/Layout';
import api from '@/services/api';

type ProviderSettings = {
  analyze_provider: string;
  resume_provider: string;
  nvidia_api_key_configured: boolean;
  ollama_base_url: string;
  ollama_model: string;
  nvidia_model: string;
};

const PROVIDERS = [
  {
    value: 'ollama',
    label: 'Ollama',
    description: 'Local model — no API key required',
    icon: '🦙',
    color: 'border-blue-200 bg-blue-50 text-blue-700',
    activeColor: 'border-blue-500 bg-blue-100 ring-2 ring-blue-400',
  },
  {
    value: 'nvidia',
    label: 'NVIDIA NIM',
    description: 'Cloud API — requires NVIDIA_API_KEY',
    icon: '⚡',
    color: 'border-green-200 bg-green-50 text-green-700',
    activeColor: 'border-green-500 bg-green-100 ring-2 ring-green-400',
  },
];

function ProviderCard({
  value,
  current,
  disabled,
  disabledReason,
  onSelect,
}: {
  value: string;
  current: string;
  disabled: boolean;
  disabledReason?: string;
  onSelect: (v: string) => void;
}) {
  const p = PROVIDERS.find(p => p.value === value)!;
  const isActive = current === value;
  const { t } = useTranslation();

  const card = (
    <button
      onClick={() => !disabled && onSelect(value)}
      disabled={disabled}
      className={`w-full text-left rounded-xl border-2 p-4 transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed
        ${isActive ? p.activeColor : 'border-muted bg-muted/30 hover:border-muted-foreground/40'}`}
    >
      <div className="flex items-center gap-3">
        <span className="text-2xl">{p.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm flex items-center gap-1.5">
            {p.label}
            {isActive && <Badge variant="secondary" className="text-xs px-1.5 py-0">{t('settings.active')}</Badge>}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">{p.description}</div>
        </div>
        {isActive && (
          <CheckCircle className="w-4 h-4 text-green-600 shrink-0" />
        )}
      </div>
    </button>
  );

  if (disabled && disabledReason) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>{card}</TooltipTrigger>
          <TooltipContent side="top"><p>{disabledReason}</p></TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }
  return card;
}

export default function Settings() {
  const [settings, setSettings] = useState<ProviderSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<'analyze' | 'resume' | 'nvidia_model' | 'ollama_model' | null>(null);
  const [editingModel, setEditingModel] = useState<string | null>(null);
  const [editingOllamaModel, setEditingOllamaModel] = useState<string | null>(null);
  const { showToast } = useToast();
  const { t } = useTranslation();

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.getProviderSettings();
      setSettings(data);
    } catch {
      showToast('error', t('settings.failedLoad'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleChange = async (field: 'analyze_provider' | 'resume_provider', value: string) => {
    if (!settings) return;
    setSaving(field === 'analyze_provider' ? 'analyze' : 'resume');
    try {
      const updated = await api.updateProviderSettings({ [field]: value });
      setSettings(prev => prev ? { ...prev, ...updated } : prev);
      showToast('success', t('settings.updatedProvider', { type: field === 'analyze_provider' ? t('settings.analysisProvider') : t('settings.resumeProvider'), value }));
    } catch (e: any) {
      showToast('error', e.message || t('settings.failedProvider'));
    } finally {
      setSaving(null);
    }
  };

  const handleSaveModel = async () => {
    if (!settings || editingModel === null) return;
    const trimmed = editingModel.trim();
    if (!trimmed) { showToast('error', t('settings.modelEmpty')); return; }
    setSaving('nvidia_model');
    try {
      const updated = await api.updateProviderSettings({ nvidia_model: trimmed });
      setSettings(prev => prev ? { ...prev, nvidia_model: updated.nvidia_model } : prev);
      setEditingModel(null);
      showToast('success', t('settings.updatedModel', { model: updated.nvidia_model }));
    } catch (e: any) {
      showToast('error', e.message || t('settings.failedModel'));
    } finally {
      setSaving(null);
    }
  };

  const handleSaveOllamaModel = async () => {
    if (!settings || editingOllamaModel === null) return;
    const trimmed = editingOllamaModel.trim();
    if (!trimmed) { showToast('error', t('settings.modelEmpty')); return; }
    setSaving('ollama_model');
    try {
      const updated = await api.updateProviderSettings({ ollama_model: trimmed });
      setSettings(prev => prev ? { ...prev, ollama_model: updated.ollama_model } : prev);
      setEditingOllamaModel(null);
      showToast('success', t('settings.updatedOllamaModel', { model: updated.ollama_model }));
    } catch (e: any) {
      showToast('error', e.message || t('settings.failedModel'));
    } finally {
      setSaving(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="w-9 h-9 rounded-lg" />
          <div className="space-y-1.5">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-4 w-64" />
          </div>
        </div>
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (!settings) return null;

  const nvidiaDisabledReason = t('settings.nvidiaDisabledReason');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="bg-primary text-primary-foreground w-9 h-9 rounded-lg flex items-center justify-center shadow-sm shrink-0">
          <Settings2 size={18} />
        </div>
        <div>
          <h1 className="text-2xl font-bold">{t('settings.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('settings.subtitle')}</p>
        </div>
        <Button variant="outline" size="sm" className="ml-auto gap-1.5" onClick={load}>
          <RefreshCw className="w-3.5 h-3.5" /> {t('settings.refresh')}
        </Button>
      </div>

      <Separator />

      {/* NVIDIA Key Status */}
      <Alert variant={settings.nvidia_api_key_configured ? 'default' : 'destructive'}
        className={settings.nvidia_api_key_configured ? 'border-green-300 bg-green-50/60 text-green-900' : 'border-yellow-300 bg-yellow-50/60 text-yellow-900'}>
        {settings.nvidia_api_key_configured
          ? <CheckCircle className="h-4 w-4 text-green-600" />
          : <AlertCircle className="h-4 w-4 text-yellow-600" />}
        <AlertTitle className="font-semibold">
          {settings.nvidia_api_key_configured ? t('settings.nvidiaKeyConfigured') : t('settings.nvidiaKeyNotConfigured')}
        </AlertTitle>
        <AlertDescription className="text-xs">
          {settings.nvidia_api_key_configured ? (
            <span>{t('settings.nvidiaActiveModel')} <code className="font-mono bg-green-100 px-1 rounded">{settings.nvidia_model}</code></span>
          ) : (
            <span>Set <code className="font-mono bg-yellow-100 px-1 rounded">NVIDIA_API_KEY</code> in <code className="font-mono bg-yellow-100 px-1 rounded">backend/.env</code> to enable NVIDIA.
              {' '}Get a free key at{' '}
              <a href="https://build.nvidia.com" target="_blank" rel="noreferrer" className="underline inline-flex items-center gap-0.5">
                build.nvidia.com <ExternalLink className="w-3 h-3" />
              </a>
            </span>
          )}
        </AlertDescription>
      </Alert>

      {/* Provider sections — side-by-side on wide screens */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Analysis Provider */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <div className="w-7 h-7 rounded-md bg-purple-100 flex items-center justify-center">
                <Bot className="w-4 h-4 text-purple-600" />
              </div>
              {t('settings.messageAnalysis')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('settings.messageAnalysisDesc')}
            </CardDescription>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>{t('settings.model')}</span>
              <code className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground">
                {settings.analyze_provider === 'nvidia' ? settings.nvidia_model : settings.ollama_model}
              </code>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {PROVIDERS.map(p => (
                <ProviderCard
                  key={p.value}
                  value={p.value}
                  current={settings.analyze_provider}
                  disabled={saving === 'analyze' || (p.value === 'nvidia' && !settings.nvidia_api_key_configured)}
                  disabledReason={p.value === 'nvidia' ? nvidiaDisabledReason : undefined}
                  onSelect={v => handleChange('analyze_provider', v)}
                />
              ))}
            </div>
            {saving === 'analyze' && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <RefreshCw className="w-3 h-3 animate-spin" /> {t('settings.saving')}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Resume Provider */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <div className="w-7 h-7 rounded-md bg-yellow-100 flex items-center justify-center">
                <Zap className="w-4 h-4 text-yellow-600" />
              </div>
              {t('settings.resumeTools')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('settings.resumeToolsDesc')}
            </CardDescription>
            <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>{t('settings.model')}</span>
              <code className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground">
                {settings.resume_provider === 'nvidia' ? settings.nvidia_model : settings.ollama_model}
              </code>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {PROVIDERS.map(p => (
                <ProviderCard
                  key={p.value}
                  value={p.value}
                  current={settings.resume_provider}
                  disabled={saving === 'resume' || (p.value === 'nvidia' && !settings.nvidia_api_key_configured)}
                  disabledReason={p.value === 'nvidia' ? nvidiaDisabledReason : undefined}
                  onSelect={v => handleChange('resume_provider', v)}
                />
              ))}
            </div>
            {saving === 'resume' && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <RefreshCw className="w-3 h-3 animate-spin" /> {t('settings.saving')}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Ollama + NVIDIA info row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-dashed">
          <CardHeader className="pb-2 pt-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <Cpu className="w-4 h-4 text-blue-500" /> {t('settings.ollamaConfig')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pb-4">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t('settings.baseUrl')}</span>
              <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">{settings.ollama_base_url}</code>
            </div>
            <div className="space-y-1.5">
              <span className="text-sm text-muted-foreground">{t('settings.model')}</span>
              {editingOllamaModel !== null ? (
                <div className="flex items-center gap-2">
                  <Input
                    value={editingOllamaModel}
                    onChange={e => setEditingOllamaModel(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleSaveOllamaModel(); if (e.key === 'Escape') setEditingOllamaModel(null); }}
                    className="h-7 text-xs font-mono"
                    autoFocus
                    disabled={saving === 'ollama_model'}
                  />
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={handleSaveOllamaModel} disabled={saving === 'ollama_model'}>
                    {saving === 'ollama_model' ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3 text-green-600" />}
                  </Button>
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingOllamaModel(null)} disabled={saving === 'ollama_model'}>
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded flex-1">{settings.ollama_model}</code>
                  <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => setEditingOllamaModel(settings.ollama_model)}>
                    <Pencil className="w-3 h-3" />
                  </Button>
                </div>
              )}
            </div>
            <p className="text-xs text-muted-foreground pt-1">
              {t('settings.ollamaEnvHint', { url: 'OLLAMA_BASE_URL', model: 'OLLAMA_MODEL', file: 'backend/.env' })}
            </p>
          </CardContent>
        </Card>

        <Card className="border-dashed">
          <CardHeader className="pb-2 pt-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="w-4 h-4 text-green-500" /> {t('settings.nvidiaConfig')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pb-4">
            <div className="space-y-1.5">
              <span className="text-sm text-muted-foreground">{t('settings.model')}</span>
              {editingModel !== null ? (
                <div className="flex items-center gap-2">
                  <Input
                    value={editingModel}
                    onChange={e => setEditingModel(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleSaveModel(); if (e.key === 'Escape') setEditingModel(null); }}
                    className="h-7 text-xs font-mono"
                    autoFocus
                    disabled={saving === 'nvidia_model'}
                  />
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={handleSaveModel} disabled={saving === 'nvidia_model'}>
                    {saving === 'nvidia_model' ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3 text-green-600" />}
                  </Button>
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setEditingModel(null)} disabled={saving === 'nvidia_model'}>
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded flex-1">{settings.nvidia_model}</code>
                  <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => setEditingModel(settings.nvidia_model)}>
                    <Pencil className="w-3 h-3" />
                  </Button>
                </div>
              )}
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">{t('settings.apiKey')}</span>
              <Badge variant={settings.nvidia_api_key_configured ? 'outline' : 'secondary'}
                className={settings.nvidia_api_key_configured ? 'border-green-400 text-green-700 text-xs' : 'text-xs'}>
                {settings.nvidia_api_key_configured ? t('settings.apiKeySet') : t('settings.apiKeyNotSet')}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground pt-1">
              {t('settings.nvidiaEnvHint', { key: 'NVIDIA_API_KEY', file: 'backend/.env' })}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
