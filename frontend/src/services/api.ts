// Use empty string for same-domain requests in production
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface Channel {
  id: number;
  username: string;
  name?: string;
  description?: string;
  is_active: boolean;
  is_listened?: number | boolean;  // Backend uses INTEGER (0/1), frontend handles both
  telegram_account_id?: number;
  message_count?: number;
  pending_count?: number;
  job_count?: number;
  last_fetch_new_count?: number;
  last_fetch_at?: string;
}

export interface Job {
  id: number;
  title?: string;
  company?: string;
  company_link?: string;
  location?: string;
  is_remote?: boolean;
  role_type?: string;
  skills?: string[] | string;
  salary?: string;
  salary_level?: string;
  category?: string;
  priority?: string;
  jd?: string;
  hr_contact?: string;
  channel_contact?: string;
  published_to_jobees?: boolean;
  published_at?: string;
  jobees_job_id?: string;
  is_applied: boolean;
  applied_at?: string;
  is_favorite: boolean;
  notes?: string;
  channel_id?: number;
  channel_name?: string;
  source_type?: string;
  website_source_id?: number;
  channel: Channel;
  message: {
    id: number;
    text?: string;
    date?: string;
    has_image?: boolean;
    sender_id?: number;
    sender_username?: string;
    sender_first_name?: string;
  };
}

export interface Developer {
  id: number;
  name?: string;
  skills?: string[];
  experience?: string;
  portfolio?: string;
  github?: string;
  linkedin?: string;
  contact?: string;
  contact_type?: string;
  summary?: string;
  looking_for_work?: boolean;
  is_contacted: boolean;
  contacted_at?: string;
  notes?: string;
  source_type?: string;
  website_source_id?: number;
  channel: Channel;
  website_source?: {
    id: number;
    name: string;
    url: string;
  };
  message: {
    id: number;
    text?: string;
    date?: string;
    has_image?: boolean;
    sender_id?: number;
    sender_username?: string;
    sender_first_name?: string;
  };
}

export interface Stats {
  total_channels: number;
  job_postings: number;
  developers: number;
  total_messages: number;
  analyzed_messages: number;
  pending_messages: number;
  skipped_messages: number;
  applications: {
    jobs: {
      total: number;
    };
  };
  ollama_available: boolean;
}

export interface TelegramAccount {
  id: number;
  api_id: number;
  phone_number: string;
  username: string | null;
  session_name: string;
  is_active: boolean;
  is_authenticated: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface WebsiteSource {
  id: number;
  name: string;
  url: string;
  site_type: string;
  is_active: boolean;
  last_fetch_new_count: number;
  last_fetch_at: string | null;
  extraction_prompt: string | null;
  cookies: string | null;
  job_count: number;
  message_count: number;
  pending_count: number;
}

const api = {
  // Stats
  getStats: async (): Promise<Stats> => {
    const response = await fetch(`${API_BASE}/api/stats`);
    return response.json();
  },

  // Channels
  getChannels: async (params?: { limit?: number; offset?: number; search?: string; is_active?: boolean }): Promise<{ channels: Channel[]; total: number; limit: number; offset: number }> => {
    const query = new URLSearchParams(params as any).toString();
    const response = await fetch(`${API_BASE}/api/channels${query ? `?${query}` : ''}`);
    return response.json();
  },

  addChannel: async (formData: FormData): Promise<void> => {
    await fetch(`${API_BASE}/api/channels`, {
      method: 'POST',
      body: formData,
    });
  },

  toggleChannel: async (id: number): Promise<void> => {
    await fetch(`${API_BASE}/api/channels/${id}/toggle`, { method: 'POST' });
  },

  deleteChannel: async (id: number): Promise<void> => {
    await fetch(`${API_BASE}/api/channels/${id}`, { method: 'DELETE' });
  },

  getTelegramDialogs: async (account_id?: number): Promise<{ success: boolean; dialogs: any[]; error?: string }> => {
    const query = account_id ? `?account_id=${account_id}` : '';
    const response = await fetch(`${API_BASE}/api/telegram-dialogs${query}`);
    return response.json();
  },

  // Telegram Accounts
  getTelegramAccounts: async (): Promise<TelegramAccount[]> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts`);
    return response.json();
  },

  createTelegramAccount: async (data: { api_id: number; api_hash: string; phone_number: string }): Promise<TelegramAccount> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to create account (${response.status})`);
    }
    return response.json();
  },

  deleteTelegramAccount: async (id: number): Promise<{ success: boolean }> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts/${id}`, { method: 'DELETE' });
    return response.json();
  },

  toggleTelegramAccountActive: async (id: number): Promise<{ success: boolean; is_active: boolean }> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts/${id}/toggle-active`, { method: 'PATCH' });
    return response.json();
  },

  startAuthentication: async (account_id: number): Promise<{ success: boolean; message: string }> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts/authenticate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id }),
    });
    return response.json();
  },

  verifyCode: async (account_id: number, code: string): Promise<{ success: boolean; message: string; needs_password?: boolean }> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id, code }),
    });
    return response.json();
  },

  verifyPassword: async (account_id: number, password: string): Promise<{ success: boolean; message: string }> => {
    const response = await fetch(`${API_BASE}/api/telegram-accounts/verify-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_id, password }),
    });
    return response.json();
  },

  // Jobs
  getJobs: async (params?: { is_applied?: string; is_favorite?: string; search?: string; limit?: number; offset?: number }): Promise<{ jobs: Job[]; total: number; limit: number; offset: number }> => {
    const query = new URLSearchParams(params as any).toString();
    const response = await fetch(`${API_BASE}/api/jobs${query ? `?${query}` : ''}`);
    return response.json();
  },

  getJob: async (id: number): Promise<{ job: Job }> => {
    const response = await fetch(`${API_BASE}/api/jobs/${id}`);
    return response.json();
  },

  toggleJobApplied: async (id: number, notes?: string): Promise<{ success: boolean }> => {
    const formData = new FormData();
    if (notes) formData.append('notes', notes);
    const response = await fetch(`${API_BASE}/api/jobs/${id}/toggle-applied`, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  },

  toggleJobFavorite: async (id: number): Promise<{ success: boolean; is_favorite: boolean }> => {
    const response = await fetch(`${API_BASE}/api/jobs/${id}/toggle-favorite`, {
      method: 'POST',
    });
    return response.json();
  },

  reviewJob: async (id: number, formData: FormData): Promise<void> => {
    await fetch(`${API_BASE}/api/jobs/${id}/review`, {
      method: 'POST',
      body: formData,
    });
  },

  deleteJob: async (id: number): Promise<{ success: boolean }> => {
    const response = await fetch(`${API_BASE}/api/jobs/${id}`, {
      method: 'DELETE',
    });
    return response.json();
  },

  bulkDeleteJobs: async (ids: number[]): Promise<{ success: boolean; deleted: number }> => {
    const response = await fetch(`${API_BASE}/api/jobs/bulk-delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    return response.json();
  },

  publishJobToJobees: async (id: number): Promise<{ success: boolean; published: number; created: number; skipped: number; failed: number; errors: string[] }> => {
    const response = await fetch(`${API_BASE}/api/jobs/${id}/publish-to-jobees`, {
      method: 'POST',
    });
    return response.json();
  },

  publishAllJobsToJobees: async (): Promise<{ success: boolean; published: number; created: number; skipped: number; failed: number; errors: string[] }> => {
    const response = await fetch(`${API_BASE}/api/jobs/publish-to-jobees/bulk`, {
      method: 'POST',
    });
    return response.json();
  },

  // Developers
  getDevelopers: async (params?: { looking_for_work?: string; is_contacted?: string; search?: string; limit?: number; offset?: number }): Promise<{ developers: Developer[]; total: number; limit: number; offset: number }> => {
    const query = new URLSearchParams(params as any).toString();
    const response = await fetch(`${API_BASE}/api/developers${query ? `?${query}` : ''}`);
    return response.json();
  },

  getDeveloper: async (id: number): Promise<{ developer: Developer }> => {
    const response = await fetch(`${API_BASE}/api/developers/${id}`);
    return response.json();
  },

  toggleDeveloperContacted: async (id: number, notes?: string): Promise<{ success: boolean; is_contacted: boolean; developer?: Developer }> => {
    const formData = new FormData();
    if (notes) formData.append('notes', notes);
    const response = await fetch(`${API_BASE}/api/developers/${id}/toggle-contacted`, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  },

  deleteDeveloper: async (id: number): Promise<{ success: boolean }> => {
    const response = await fetch(`${API_BASE}/api/developers/${id}`, {
      method: 'DELETE',
    });
    return response.json();
  },

  bulkDeleteDevelopers: async (ids: number[]): Promise<{ success: boolean; deleted: number }> => {
    const response = await fetch(`${API_BASE}/api/developers/bulk-delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    return response.json();
  },

  reviewDeveloper: async (id: number, formData: FormData): Promise<void> => {
    await fetch(`${API_BASE}/api/developers/${id}/review`, {
      method: 'POST',
      body: formData,
    });
  },

  // Messages
  getMessage: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/messages/${id}`);
    return response.json();
  },

  getMessages: async (params?: { channel_id?: number; website_source_id?: number; search?: string; analysis_status?: string; limit?: number; offset?: number }): Promise<any> => {
    const queryParams = new URLSearchParams();
    if (params?.channel_id) queryParams.append('channel_id', params.channel_id.toString());
    if (params?.website_source_id) queryParams.append('website_source_id', params.website_source_id.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.analysis_status) queryParams.append('analysis_status', params.analysis_status);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset) queryParams.append('offset', params.offset.toString());
    const response = await fetch(`${API_BASE}/api/messages?${queryParams.toString()}`);
    return response.json();
  },

  // Actions
  fetchChannel: async (id: number, account_id?: number): Promise<any> => {
    const query = account_id ? `?account_id=${account_id}` : '';
    const response = await fetch(`${API_BASE}/api/fetch/${id}${query}`, { method: 'POST' });
    return response.json();
  },

  analyzeChannel: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/analyze/${id}`, { method: 'POST' });
    return response.json();
  },

  fetchAll: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/fetch-all`, { method: 'POST' });
    return response.json();
  },

  analyzeAll: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/analyze-all`, { method: 'POST' });
    return response.json();
  },

  stopBulkOperation: async (operation_id: string): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/bulk/stop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operation_id }),
    });
    return response.json();
  },

  reanalyzeMessage: async (messageId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/reanalyze-message/${messageId}`, { method: 'POST' });
    return response.json();
  },

  deleteMessage: async (messageId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/messages/${messageId}`, { method: 'DELETE' });
    return response.json();
  },

  bulkDeleteMessages: async (ids: number[]): Promise<{ success: boolean; deleted: number }> => {
    const response = await fetch(`${API_BASE}/api/messages/bulk-delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    });
    return response.json();
  },

  toggleSkipMessage: async (messageId: number): Promise<{ success: boolean; is_manual_skip: boolean; analysis_status: string }> => {
    const response = await fetch(`${API_BASE}/api/messages/${messageId}/toggle-skip`, { method: 'POST' });
    return response.json();
  },

  stopAnalyze: async (channelId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/stop-analyze?channel_id=${channelId}`, { method: 'POST' });
    return response.json();
  },

  startCron: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/cron/start`, { method: 'POST' });
    return response.json();
  },

  stopCron: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/cron/stop`, { method: 'POST' });
    return response.json();
  },

  getCronStatus: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/cron/status`);
    return response.json();
  },

  getAutoAnalyze: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/auto-analyze`);
    return response.json();
  },

  setAutoAnalyze: async (enabled: boolean): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/auto-analyze?enabled=${enabled}`, {
      method: 'POST',
    });
    return response.json();
  },

  cleanupOldMessages: async (days: number = 30): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/cleanup/old-messages?days=${days}`, { method: 'POST' });
    return response.json();
  },

  getDailyJobs: async (days: number = 30): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/daily-jobs?days=${days}`);
    return response.json();
  },

  getDailyDevelopersContacted: async (days: number = 30): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/daily-developers-contacted?days=${days}`);
    return response.json();
  },

  getDailyJobsApplied: async (days: number = 30): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/daily-jobs-applied?days=${days}`);
    return response.json();
  },

  getDailyStatsTable: async (days: number = 7): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/daily-stats-table?days=${days}`);
    return response.json();
  },

  startListener: async (channelUsernames: string[], autoAnalyze: boolean = false, telegramAccountId?: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/listener/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_usernames: channelUsernames,
        auto_analyze: autoAnalyze,
        telegram_account_id: telegramAccountId,
      }),
    });
    return response.json();
  },

  stopListener: async (telegramAccountId?: number): Promise<any> => {
    const url = telegramAccountId
      ? `${API_BASE}/api/listener/stop?telegram_account_id=${telegramAccountId}`
      : `${API_BASE}/api/listener/stop`;
    const response = await fetch(url, { method: 'POST' });
    return response.json();
  },

  getListenerStatus: async (telegramAccountId?: number): Promise<any> => {
    const url = telegramAccountId
      ? `${API_BASE}/api/listener/status?telegram_account_id=${telegramAccountId}`
      : `${API_BASE}/api/listener/status`;
    const response = await fetch(url);
    return response.json();
  },

  addListenerChannels: async (channelUsernames: string[], telegramAccountId?: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/listener/add-channels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_usernames: channelUsernames,
        telegram_account_id: telegramAccountId,
      }),
    });
    return response.json();
  },

  removeListenerChannels: async (channelUsernames: string[], telegramAccountId?: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/listener/remove-channels`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channel_usernames: channelUsernames,
        telegram_account_id: telegramAccountId,
      }),
    });
    return response.json();
  },

  getListenerChannels: async (telegramAccountId?: number): Promise<any> => {
    const url = telegramAccountId
      ? `${API_BASE}/api/listener/channels?telegram_account_id=${telegramAccountId}`
      : `${API_BASE}/api/listener/channels`;
    const response = await fetch(url);
    return response.json();
  },

  getOperations: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/operations`);
    return response.json();
  },

  getCurrentAnalyzing: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/operations/current-analyzing`);
    return response.json();
  },

  getOperation: async (operationId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/operations/${operationId}`);
    return response.json();
  },

  // Website Sources
  getWebsiteSources: async (): Promise<{ success: boolean; sources: WebsiteSource[] }> => {
    const response = await fetch(`${API_BASE}/api/website-sources`);
    return response.json();
  },

  addWebsiteSource: async (formData: FormData): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/website-sources`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to add website source (${response.status})`);
    }
    return response.json();
  },

  deleteWebsiteSource: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/website-sources/${id}`, { method: 'DELETE' });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to delete website source (${response.status})`);
    }
    return response.json();
  },

  fetchWebsiteSource: async (id: number, days_back: number = 0): Promise<any> => {
    const formData = new FormData();
    formData.append('days_back', days_back.toString());
    const response = await fetch(`${API_BASE}/api/website-sources/${id}/fetch`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to fetch website source (${response.status})`);
    }
    return response.json();
  },

  fetchAllWebsiteSources: async (days_back: number = 0): Promise<any> => {
    const formData = new FormData();
    formData.append('days_back', days_back.toString());
    const response = await fetch(`${API_BASE}/api/website-sources/fetch-all`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to fetch all website sources (${response.status})`);
    }
    return response.json();
  },

  analyzeWebsiteSource: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/website-sources/${id}/analyze`, { method: 'POST' });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to analyze website source (${response.status})`);
    }
    return response.json();
  },

  analyzeAllWebsiteSources: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/website-sources/analyze-all`, { method: 'POST' });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to analyze all website sources (${response.status})`);
    }
    return response.json();
  },

  updateWebsiteSource: async (id: number, formData: FormData): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/website-sources/${id}`, {
      method: 'PUT',
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Failed to update website source (${response.status})`);
    }
    return response.json();
  },

  toggleWebsiteSource: async (id: number): Promise<any> => {
    const formData = new FormData();
    formData.append('is_active', 'true');
    const response = await fetch(`${API_BASE}/api/website-sources/${id}/toggle`, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  },

  stopWebsiteSource: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/website-sources/${id}/stop`, { method: 'POST' });
    return response.json();
  },

  enhanceResume: async (jobId: number | null, resumeText: string, onChunk: (text: string) => void, messageText?: string): Promise<void> => {
    const body: any = { resume_text: resumeText };
    if (jobId) body.job_id = jobId;
    if (messageText) body.message_text = messageText;
    const response = await fetch(`${API_BASE}/api/resume/enhance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Resume enhancement failed: ${response.status}`);
    }
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const data = line.slice(5).trim();
        if (data === '[DONE]') return;
        try {
          const chunk = JSON.parse(data);
          if (chunk.error) throw new Error(chunk.error);
          if (chunk.content) onChunk(chunk.content);
        } catch (e: any) {
          if (e.message && !e.message.startsWith('JSON')) throw e;
        }
      }
    }
  },

  scoreResume: async (jobId: number | null, resumeText: string, messageText?: string): Promise<{
    score: number;
    level: string;
    summary: string;
    matched_skills: string[];
    missing_skills: string[];
    strengths: string[];
    improvements: string[];
  }> => {
    const response = await fetch(`${API_BASE}/api/resume/score`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(jobId ? { job_id: jobId, resume_text: resumeText } : { message_text: messageText, resume_text: resumeText }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Score failed: ${response.status}`);
    }
    const data = await response.json();
    return data.result;
  },

  generateResume: async (jobId: number | null, onChunk: (text: string) => void, messageText?: string): Promise<void> => {
    const body: any = {};
    if (jobId) body.job_id = jobId;
    if (messageText) body.message_text = messageText;
    const response = await fetch(`${API_BASE}/api/resume/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Resume generation failed: ${response.status}`);
    }
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.startsWith('data:')) continue;
        const data = line.slice(5).trim();
        if (data === '[DONE]') return;
        try {
          const chunk = JSON.parse(data);
          if (chunk.error) throw new Error(chunk.error);
          if (chunk.content) onChunk(chunk.content);
        } catch (e: any) {
          if (e.message && !e.message.startsWith('JSON')) throw e;
        }
      }
    }
  },

  getResumeProvider: async (): Promise<{ provider: string; model: string; nvidia_configured: boolean }> => {
    const response = await fetch(`${API_BASE}/api/resume/provider`);
    if (!response.ok) throw new Error('Failed to fetch resume provider');
    return response.json();
  },

  getProviderSettings: async (): Promise<{
    analyze_provider: string;
    resume_provider: string;
    nvidia_api_key_configured: boolean;
    ollama_base_url: string;
    ollama_model: string;
    nvidia_model: string;
  }> => {
    const response = await fetch(`${API_BASE}/api/settings/providers`);
    if (!response.ok) throw new Error('Failed to fetch provider settings');
    return response.json();
  },

  updateProviderSettings: async (settings: {
    analyze_provider?: string;
    resume_provider?: string;
    nvidia_model?: string;
    ollama_model?: string;
  }): Promise<{ analyze_provider: string; resume_provider: string; nvidia_model: string; ollama_model: string }> => {
    const response = await fetch(`${API_BASE}/api/settings/providers`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update provider settings');
    }
    return response.json();
  },

  listResumes: async (params?: { resume_type?: string; limit?: number; offset?: number }): Promise<{ resumes: any[] }> => {
    const queryParams = new URLSearchParams();
    if (params?.resume_type) queryParams.append('resume_type', params.resume_type);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset) queryParams.append('offset', params.offset.toString());
    const response = await fetch(`${API_BASE}/api/resumes?${queryParams.toString()}`);
    if (!response.ok) throw new Error('Failed to fetch resumes');
    return response.json();
  },

  getResume: async (resumeId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/resumes/${resumeId}`);
    if (!response.ok) throw new Error('Failed to fetch resume');
    return response.json();
  },

  deleteResume: async (resumeId: number): Promise<{ success: boolean; message: string }> => {
    const response = await fetch(`${API_BASE}/api/resumes/${resumeId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete resume');
    return response.json();
  },
};

export default api;
