// Use empty string for same-domain requests in production
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

export interface Channel {
  id: number;
  username: string;
  name?: string;
  description?: string;
  is_active: boolean;
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
  skills?: string[];
  contact?: string;
  contact_type?: string;
  summary?: string;
  translated_text?: string;
  confidence?: string;
  is_applied: boolean;
  is_reviewed: boolean;
  is_approved: boolean;
  notes?: string;
  analyzed_at?: string;
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
  translated_text?: string;
  confidence?: string;
  looking_for_work?: boolean;
  is_contacted: boolean;
  is_reviewed: boolean;
  is_approved: boolean;
  notes?: string;
  analyzed_at?: string;
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

  getTelegramDialogs: async (): Promise<{ success: boolean; dialogs: any[]; error?: string }> => {
    const response = await fetch(`${API_BASE}/api/telegram-dialogs`);
    return response.json();
  },

  // Jobs
  getJobs: async (params?: { remote?: string; search?: string; limit?: number; offset?: number }): Promise<{ jobs: Job[]; total: number; limit: number; offset: number }> => {
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

  reviewJob: async (id: number, formData: FormData): Promise<void> => {
    await fetch(`${API_BASE}/api/jobs/${id}/review`, {
      method: 'POST',
      body: formData,
    });
  },

  // Developers
  getDevelopers: async (params?: { looking_for_work?: string; search?: string; limit?: number; offset?: number }): Promise<{ developers: Developer[]; total: number; limit: number; offset: number }> => {
    const query = new URLSearchParams(params as any).toString();
    const response = await fetch(`${API_BASE}/api/developers${query ? `?${query}` : ''}`);
    return response.json();
  },

  getDeveloper: async (id: number): Promise<{ developer: Developer }> => {
    const response = await fetch(`${API_BASE}/api/developers/${id}`);
    return response.json();
  },

  toggleDeveloperContacted: async (id: number, notes?: string): Promise<{ success: boolean }> => {
    const formData = new FormData();
    if (notes) formData.append('notes', notes);
    const response = await fetch(`${API_BASE}/api/developers/${id}/toggle-contacted`, {
      method: 'POST',
      body: formData,
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
  getMessages: async (params?: { channel_id?: number; search?: string; analysis_status?: string; limit?: number; offset?: number }): Promise<any> => {
    const queryParams = new URLSearchParams();
    if (params?.channel_id) queryParams.append('channel_id', params.channel_id.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.analysis_status) queryParams.append('analysis_status', params.analysis_status);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset) queryParams.append('offset', params.offset.toString());
    const response = await fetch(`${API_BASE}/api/messages?${queryParams.toString()}`);
    return response.json();
  },

  // Actions
  fetchChannel: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/fetch/${id}`, { method: 'POST' });
    return response.json();
  },

  analyzeChannel: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/analyze/${id}`, { method: 'POST' });
    return response.json();
  },

  fetchAnalyzeChannel: async (id: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/fetch-analyze/${id}`, { method: 'POST' });
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

  fetchAnalyzeAll: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/fetch-analyze-all`, { method: 'POST' });
    return response.json();
  },

  reanalyzeMessages: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/reanalyze`, { method: 'POST' });
    return response.json();
  },

  reanalyzeSkipped: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/reanalyze-skipped`, { method: 'POST' });
    return response.json();
  },

  reanalyzeMessage: async (messageId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/reanalyze-message/${messageId}`, { method: 'POST' });
    return response.json();
  },

  stopAnalyze: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/stop-analyze`, { method: 'POST' });
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

  getOperations: async (): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/operations`);
    return response.json();
  },

  getOperation: async (operationId: number): Promise<any> => {
    const response = await fetch(`${API_BASE}/api/operations/${operationId}`);
    return response.json();
  },
};

export default api;
