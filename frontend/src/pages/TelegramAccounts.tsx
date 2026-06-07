import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle } from 'lucide-react';
import api from '@/services/api';
import { useToast } from '@/components/Layout';

interface TelegramAccount {
  id: number;
  api_id: number;
  phone_number: string;
  session_name: string;
  is_active: boolean;
  is_authenticated: boolean;
  created_at: string;
  last_used_at: string | null;
}

const TelegramAccounts = () => {
  const [accounts, setAccounts] = useState<TelegramAccount[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newAccount, setNewAccount] = useState({ api_id: '', api_hash: '', phone_number: '' });
  const { showToast } = useToast();

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const data = await api.getTelegramAccounts();
      setAccounts(data);
    } catch (error) {
      console.error('Failed to load accounts:', error);
      showToast('error', 'Failed to load Telegram accounts');
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
      showToast('success', 'Telegram account added successfully');
      setNewAccount({ api_id: '', api_hash: '', phone_number: '' });
      setShowAddForm(false);
      loadAccounts();
    } catch (error) {
      console.error('Failed to add account:', error);
      showToast('error', 'Failed to add Telegram account');
    }
  };

  const handleDeleteAccount = async (id: number) => {
    if (!confirm('Are you sure you want to delete this account?')) return;
    try {
      await api.deleteTelegramAccount(id);
      showToast('success', 'Telegram account deleted');
      loadAccounts();
    } catch (error) {
      console.error('Failed to delete account:', error);
      showToast('error', 'Failed to delete Telegram account');
    }
  };

  const handleToggleActive = async (id: number) => {
    try {
      await api.toggleTelegramAccountActive(id);
      showToast('success', 'Account status updated');
      loadAccounts();
    } catch (error) {
      console.error('Failed to toggle account:', error);
      showToast('error', 'Failed to update account status');
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Telegram Accounts</h1>
          <p className="text-muted-foreground">Manage your Telegram accounts for fetching messages</p>
        </div>
        <Button onClick={() => setShowAddForm(!showAddForm)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Account
        </Button>
      </div>

      {showAddForm && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Add New Telegram Account</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAddAccount} className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-1 block">API ID</label>
                <Input
                  type="number"
                  placeholder="Enter API ID from my.telegram.org"
                  value={newAccount.api_id}
                  onChange={(e) => setNewAccount({ ...newAccount, api_id: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">API Hash</label>
                <Input
                  type="password"
                  placeholder="Enter API Hash from my.telegram.org"
                  value={newAccount.api_hash}
                  onChange={(e) => setNewAccount({ ...newAccount, api_hash: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-1 block">Phone Number</label>
                <Input
                  type="tel"
                  placeholder="+1234567890"
                  value={newAccount.phone_number}
                  onChange={(e) => setNewAccount({ ...newAccount, phone_number: e.target.value })}
                  required
                />
              </div>
              <div className="flex gap-2">
                <Button type="submit">Add Account</Button>
                <Button type="button" variant="outline" onClick={() => setShowAddForm(false)}>
                  Cancel
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
            No Telegram accounts configured. Add an account to start fetching messages.
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
                      <h3 className="font-semibold">{account.phone_number}</h3>
                      <Badge variant={account.is_active ? 'default' : 'secondary'}>
                        {account.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                      {account.is_authenticated ? (
                        <Badge variant="outline" className="border-green-500 text-green-700">
                          <CheckCircle className="w-3 h-3 mr-1" />
                          Authenticated
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="border-yellow-500 text-yellow-700">
                          <XCircle className="w-3 h-3 mr-1" />
                          Not Authenticated
                        </Badge>
                      )}
                    </div>
                    <div className="text-sm text-muted-foreground space-y-1">
                      <p>API ID: {account.api_id}</p>
                      <p>Session: {account.session_name}</p>
                      <p>Added: {new Date(account.created_at).toLocaleDateString()}</p>
                      {account.last_used_at && (
                        <p>Last used: {new Date(account.last_used_at).toLocaleString()}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggleActive(account.id)}
                    >
                      {account.is_active ? 'Deactivate' : 'Activate'}
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
    </div>
  );
};

export default TelegramAccounts;
