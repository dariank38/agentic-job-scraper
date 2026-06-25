import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle, Key, Radio, ShieldCheck, ShieldOff } from 'lucide-react';
import api from '@/services/api';
import type { TelegramAccount } from '@/services/api';
import { useToast } from '@/components/Layout';

const TelegramAccounts = () => {
  const { t } = useTranslation();
  const [accounts, setAccounts] = useState<TelegramAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newAccount, setNewAccount] = useState({ api_id: '', api_hash: '', phone_number: '' });
  const [authDialogOpen, setAuthDialogOpen] = useState(false);
  const [authAccountId, setAuthAccountId] = useState<number | null>(null);
  const [authStep, setAuthStep] = useState<'code' | 'password'>('code');
  const [authCode, setAuthCode] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const { showToast } = useToast();

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const data = await api.getTelegramAccounts();
      setAccounts(data);
    } catch (error) {
      showToast('error', `${t('common.failedToLoad')} ${t('telegramAccounts.title')}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAccounts();
  }, []);

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdding(true);
    try {
      await api.createTelegramAccount({
        api_id: parseInt(newAccount.api_id),
        api_hash: newAccount.api_hash,
        phone_number: newAccount.phone_number,
      });
      showToast('success', t('telegramAccounts.addedSuccessfully'));
      setNewAccount({ api_id: '', api_hash: '', phone_number: '' });
      setShowAddForm(false);
      loadAccounts();
    } catch (error) {
      const message = error instanceof Error ? error.message : `${t('common.failedToAdd')} ${t('telegramAccounts.title')}`;
      showToast('error', message);
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm(t('telegramAccounts.deleteConfirm'))) return;
    try {
      await api.deleteTelegramAccount(id);
      showToast('success', t('telegramAccounts.deletedSuccessfully'));
      loadAccounts();
    } catch (error) {
      showToast('error', `${t('common.failedToDelete')} ${t('telegramAccounts.title')}`);
    }
  };

  const handleToggleActive = async (id: number) => {
    try {
      await api.toggleTelegramAccountActive(id);
      showToast('success', t('telegramAccounts.statusUpdated'));
      loadAccounts();
    } catch (error) {
      showToast('error', `${t('common.failedToUpdate')} ${t('telegramAccounts.title')} status`);
    }
  };

  const handleStartAuth = (accountId: number) => {
    setAuthAccountId(accountId);
    setAuthStep('code');
    setAuthCode('');
    setAuthPassword('');
    setAuthDialogOpen(true);
  };

  const handleSendCode = async () => {
    if (!authAccountId) return;
    try {
      setAuthLoading(true);
      const result = await api.startAuthentication(authAccountId);
      if (result.success) {
        showToast('success', result.message);
      }
    } catch (e: any) {
      let errorMessage = t('common.failedToSend');
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!authAccountId || !authCode) return;
    try {
      setAuthLoading(true);
      const result = await api.verifyCode(authAccountId, authCode);
      if (result.success) {
        showToast('success', result.message);
        setAuthDialogOpen(false);
        loadAccounts();
      } else if (result.needs_password) {
        setAuthStep('password');
        showToast('info', result.message);
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToVerify')} ${t('telegramAccounts.verificationCode')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyPassword = async () => {
    if (!authAccountId || !authPassword) return;
    try {
      setAuthLoading(true);
      const result = await api.verifyPassword(authAccountId, authPassword);
      if (result.success) {
        showToast('success', result.message);
        setAuthDialogOpen(false);
        loadAccounts();
      }
    } catch (e: any) {
      let errorMessage = `${t('common.failedToVerify')} ${t('telegramAccounts.twoFactorPassword')}`;
      if (e.response) {
        const errorData = await e.response.json().catch(() => ({}));
        errorMessage = errorData.detail || errorMessage;
      } else if (e.message) {
        errorMessage = e.message;
      }
      showToast('error', errorMessage);
    } finally {
      setAuthLoading(false);
    }
  };

  const getInitials = (account: TelegramAccount) => {
    const name = account.username || account.phone_number || '?';
    return name.replace('@', '').slice(0, 2).toUpperCase();
  };

  return (
    <TooltipProvider>
    <div className="space-y-5">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-sky-600 via-blue-600 to-indigo-600 p-5 text-white shadow-lg">
        <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, white 1px, transparent 1px), radial-gradient(circle at 80% 20%, white 1px, transparent 1px)', backgroundSize: '40px 40px' }} />
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Radio className="w-5 h-5" />
              <h1 className="text-xl font-bold tracking-tight">{t('telegramAccounts.title')}</h1>
            </div>
            <p className="text-white/70 text-sm">{t('telegramAccounts.manageAccountsHint')}</p>
          </div>
          <div className="flex gap-2">
            <Button
              className="bg-white/20 hover:bg-white/30 text-white border border-white/30 backdrop-blur-sm h-9"
              size="sm" onClick={loadAccounts} disabled={loading}
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
              {t('common.refresh')}
            </Button>
            <Button
              className="bg-white text-sky-700 hover:bg-white/90 border-0 h-9"
              size="sm" onClick={() => setShowAddForm(!showAddForm)}
            >
              <Plus className="w-4 h-4 mr-1.5" />
              {t('telegramAccounts.addAccount')}
            </Button>
          </div>
        </div>
      </div>

      {/* Add Account Form */}
      {showAddForm && (
        <Card className="border-primary/30 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">{t('telegramAccounts.addAccount')}</CardTitle>
            <CardDescription className="text-xs">
              {t('telegramAccounts.apiDocsHint')}{' '}
              <a href="https://my.telegram.org/apps" target="_blank" rel="noreferrer" className="underline">{t('telegramAccounts.apiDocsLink')}</a>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddAccount}>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="text-sm font-medium mb-1.5 block">{t('telegramAccounts.apiId')}</label>
                  <Input
                    type="number"
                    placeholder={t('telegramAccounts.apiIdPlaceholder')}
                    value={newAccount.api_id}
                    onChange={(e) => setNewAccount({ ...newAccount, api_id: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1.5 block">{t('telegramAccounts.apiHash')}</label>
                  <Input
                    type="password"
                    placeholder={t('telegramAccounts.apiHashPlaceholder')}
                    value={newAccount.api_hash}
                    onChange={(e) => setNewAccount({ ...newAccount, api_hash: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="text-sm font-medium mb-1.5 block">{t('telegramAccounts.phone')}</label>
                  <Input
                    type="tel"
                    placeholder={t('telegramAccounts.phonePlaceholder')}
                    value={newAccount.phone_number}
                    onChange={(e) => setNewAccount({ ...newAccount, phone_number: e.target.value })}
                    required
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" size="sm" disabled={adding}>
                  {adding && <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
                  {t('telegramAccounts.addAccount')}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setShowAddForm(false)} disabled={adding}>
                  {t('common.cancel')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Accounts Table */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">
              Accounts
              {!loading && (
                <span className="ml-2 text-sm font-normal text-muted-foreground">({accounts.length})</span>
              )}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-3">
              {[1,2,3].map(i => (
                <div key={i} className="flex items-center gap-3">
                  <Skeleton className="w-9 h-9 rounded-full" />
                  <div className="space-y-1.5 flex-1">
                    <Skeleton className="h-4 w-32" />
                    <Skeleton className="h-3 w-48" />
                  </div>
                  <Skeleton className="h-8 w-24" />
                </div>
              ))}
            </div>
          ) : accounts.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              <Radio className="w-8 h-8 mx-auto mb-3 opacity-30" />
              <p className="text-sm">{t('telegramAccounts.noAccountsHint')}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">{t('common.account')}</TableHead>
                  <TableHead>{t('common.session')}</TableHead>
                  <TableHead>{t('common.status')}</TableHead>
                  <TableHead>{t('common.added')}</TableHead>
                  <TableHead>{t('common.lastUsed')}</TableHead>
                  <TableHead className="text-right pr-6">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.map((account) => (
                  <TableRow key={account.id}>
                    <TableCell className="pl-6">
                      <div className="flex items-center gap-3">
                        <Avatar className="w-8 h-8">
                          <AvatarFallback className="text-xs font-semibold bg-primary/10 text-primary">
                            {getInitials(account)}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium text-sm">{account.username ? `@${account.username}` : account.phone_number}</p>
                          <p className="text-xs text-muted-foreground">API ID: {account.api_id}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{account.session_name}</code>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        <Badge variant={account.is_active ? 'default' : 'secondary'} className="text-xs w-fit">
                          {account.is_active ? t('telegramAccounts.active') : t('telegramAccounts.inactive')}
                        </Badge>
                        {account.is_authenticated ? (
                          <span className="flex items-center gap-1 text-xs text-green-700">
                            <ShieldCheck className="w-3 h-3" /> {t('telegramAccounts.authenticated')}
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-yellow-600">
                            <ShieldOff className="w-3 h-3" /> {t('telegramAccounts.notAuthenticated')}
                          </span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(account.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {account.last_used_at ? new Date(account.last_used_at).toLocaleString() : '—'}
                    </TableCell>
                    <TableCell className="text-right pr-6">
                      <div className="flex items-center justify-end gap-1">
                        {!account.is_authenticated && (
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <Button variant="outline" size="sm" className="h-8 gap-1" onClick={() => handleStartAuth(account.id)}>
                                <Key className="w-3.5 h-3.5" />
                                {t('telegramAccounts.authenticate')}
                              </Button>
                            </TooltipTrigger>
                            <TooltipContent>{t('telegramAccounts.authenticateTooltip')}</TooltipContent>
                          </Tooltip>
                        )}
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button variant="outline" size="sm" className="h-8" onClick={() => handleToggleActive(account.id)}>
                              {account.is_active
                                ? <XCircle className="w-3.5 h-3.5 text-yellow-600" />
                                : <CheckCircle className="w-3.5 h-3.5 text-green-600" />}
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{account.is_active ? t('telegramAccounts.deactivate') : t('telegramAccounts.activate')}</TooltipContent>
                        </Tooltip>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 text-destructive hover:text-destructive hover:bg-destructive/10" onClick={() => handleDeleteAccount(account.id)}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('common.deleteAccount')}</TooltipContent>
                        </Tooltip>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={authDialogOpen} onOpenChange={setAuthDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Key className="w-4 h-4" />
              {authStep === 'code' ? t('telegramAccounts.enterVerificationCode') : t('telegramAccounts.enter2faPassword')}
            </DialogTitle>
          </DialogHeader>

          {/* Step indicator */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className={`flex items-center gap-1 ${authStep === 'code' ? 'text-primary font-medium' : 'line-through opacity-50'}`}>
              <span className="w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] font-bold border-primary text-primary">1</span>
              {t('common.verificationCode')}
            </span>
            <Separator className="flex-1" />
            <span className={`flex items-center gap-1 ${authStep === 'password' ? 'text-primary font-medium' : 'opacity-40'}`}>
              <span className={`w-5 h-5 rounded-full border-2 flex items-center justify-center text-[10px] font-bold ${authStep === 'password' ? 'border-primary text-primary' : 'border-muted-foreground text-muted-foreground'}`}>2</span>
              {t('common.twoFactorPassword')}
            </span>
          </div>

          <div className="space-y-3 pt-1">
            {authStep === 'code' ? (
              <>
                <p className="text-sm text-muted-foreground">{t('telegramAccounts.verificationCodeHint')}</p>
                <div className="flex gap-2">
                  <Input
                    placeholder={t('telegramAccounts.enterCodePlaceholder')}
                    value={authCode}
                    onChange={(e) => setAuthCode(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleVerifyCode()}
                    autoFocus
                  />
                  <Button variant="outline" onClick={handleSendCode} disabled={authLoading}>
                    {t('telegramAccounts.resendCode')}
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">{t('telegramAccounts.twoFaHint')}</p>
                <Input
                  type="password"
                  placeholder={t('telegramAccounts.enter2faPlaceholder')}
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleVerifyPassword()}
                  autoFocus
                />
              </>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setAuthDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button
              onClick={authStep === 'code' ? handleVerifyCode : handleVerifyPassword}
              disabled={authLoading || (authStep === 'code' ? !authCode : !authPassword)}
              className="gap-1.5"
            >
              {authLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
              {authLoading ? t('telegramAccounts.authenticating') : t('telegramAccounts.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
    </TooltipProvider>
  );
};

export default TelegramAccounts;
