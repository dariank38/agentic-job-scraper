import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle, Key } from 'lucide-react';
import api from '@/services/api';
import type { TelegramAccount } from '@/services/api';
import { useToast } from '@/components/Layout';

const TelegramAccounts = () => {
  const { t } = useTranslation();
  const [accounts, setAccounts] = useState<TelegramAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
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
      showToast('error', `${t('common.failedToAdd')} ${t('telegramAccounts.title')}`);
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

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">{t('telegramAccounts.title')}</h1>
          <p className="text-muted-foreground">{t('telegramAccounts.manageAccountsHint')}</p>
        </div>
        <Button onClick={() => setShowAddForm(!showAddForm)}>
          <Plus className="w-4 h-4 mr-2" />
          {t('telegramAccounts.addAccount')}
        </Button>
      </div>

      {showAddForm && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>{t('telegramAccounts.addAccount')}</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddAccount} className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-1 block">{t('telegramAccounts.apiId')}</label>
                <Input
                  type="number"
                  placeholder="Enter API ID from my.telegram.org"
                  value={newAccount.api_id}
                  onChange={(e) => setNewAccount({ ...newAccount, api_id: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">{t('telegramAccounts.apiHash')}</label>
                <Input
                  type="password"
                  placeholder="Enter API Hash from my.telegram.org"
                  value={newAccount.api_hash}
                  onChange={(e) => setNewAccount({ ...newAccount, api_hash: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">{t('telegramAccounts.phone')}</label>
                <Input
                  type="tel"
                  placeholder="+1234567890"
                  value={newAccount.phone_number}
                  onChange={(e) => setNewAccount({ ...newAccount, phone_number: e.target.value })}
                  required
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit">{t('telegramAccounts.addAccount')}</Button>
                <Button type="button" variant="outline" onClick={() => setShowAddForm(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="w-6 h-6 animate-spin" />
        </div>
      ) : accounts.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            {t('telegramAccounts.noAccountsHint')}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {accounts.map((account) => (
            <Card key={account.id}>
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="font-semibold">{account.username ? `@${account.username}` : account.phone_number}</h3>
                      <Badge variant={account.is_active ? 'default' : 'secondary'}>
                        {account.is_active ? t('telegramAccounts.active') : t('telegramAccounts.inactive')}
                      </Badge>
                      {account.is_authenticated ? (
                        <Badge variant="outline" className="border-green-500 text-green-700">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          {t('telegramAccounts.authenticated')}
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="border-yellow-500 text-yellow-700">
                          <XCircle className="w-3 h-3 mr-1" />
                          {t('telegramAccounts.notAuthenticated')}
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>{t('telegramAccounts.apiIdLabel')}: {account.api_id}</p>
                      <p>{t('telegramAccounts.sessionLabel')}: {account.session_name}</p>
                      <p>{t('telegramAccounts.addedLabel')}: {new Date(account.created_at).toLocaleDateString()}</p>
                      {account.last_used_at && (
                        <p>{t('telegramAccounts.lastUsedLabel')}: {new Date(account.last_used_at).toLocaleString()}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {!account.is_authenticated && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleStartAuth(account.id)}
                      >
                        <Key className="w-4 h-4 mr-1" />
                        {t('telegramAccounts.authenticate')}
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggleActive(account.id)}
                    >
                      {account.is_active ? t('telegramAccounts.deactivate') : t('telegramAccounts.activate')}
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleDeleteAccount(account.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={authDialogOpen} onOpenChange={setAuthDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {authStep === 'code' ? t('telegramAccounts.enterVerificationCode') : t('telegramAccounts.enter2faPassword')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {authStep === 'code' ? (
              <>
                <p className="text-sm text-muted-foreground">
                  {t('telegramAccounts.verificationCodeHint')}
                </p>
                <div className="flex gap-2">
                  <Input
                    placeholder={t('telegramAccounts.enterCodePlaceholder')}
                    value={authCode}
                    onChange={(e) => setAuthCode(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleVerifyCode()}
                  />
                  <Button onClick={handleSendCode} disabled={authLoading}>
                    {t('telegramAccounts.resendCode')}
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  {t('telegramAccounts.twoFaHint')}
                </p>
                <Input
                  type="password"
                  placeholder={t('telegramAccounts.enter2faPlaceholder')}
                  value={authPassword}
                  onChange={(e) => setAuthPassword(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleVerifyPassword()}
                />
              </>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAuthDialogOpen(false)}>
              {t('common.cancel')}
            </Button>
            <Button onClick={authStep === 'code' ? handleVerifyCode : handleVerifyPassword} disabled={authLoading}>
              {authLoading ? t('telegramAccounts.authenticating') : authStep === 'code' ? t('telegramAccounts.submit') : t('telegramAccounts.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default TelegramAccounts;
