import { useEffect, useRef, useState } from 'react';

export interface MessageResult {
  message_id: number;
  status: 'success' | 'failed' | 'other' | 'json_cutoff';
  category?: string;
  confidence?: string;
  error?: string;
}

export interface TokenUsage {
  input: number;
  output: number;
  total: number;
}

export interface NewJobNotification {
  job_id: number;
  title: string;
  company: string;
  channel: string;
  is_remote?: boolean;
  location?: string;
  role_type?: string;
}

export interface ProgressUpdate {
  type: 'fetch_start' | 'fetch_progress' | 'fetch_complete' | 'analyze_start' | 'analyze_progress' | 'analyze_complete' | 'error' | 'new_job' | 'analyzing_message' | 'stats_update' | 'cron_status' | 'listener_status' | 'channel_update' | 'bulk_fetch_start' | 'bulk_fetch_progress' | 'bulk_fetch_complete' | 'bulk_fetch_stopped';
  channel?: string;
  channel_id?: number;
  operation_id?: number | string;
  status?: string;
  count?: number;
  total?: number;
  total_messages?: number;
  current?: number;
  analyzed?: number;
  processed?: number;
  jobs?: number;
  jobs_found?: number;
  developers?: number;
  developers_found?: number;
  error?: string;
  tokens?: TokenUsage;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  message_results?: MessageResult[];
  new_job?: NewJobNotification;
  message_id?: number;
  message_text?: string;
  message_preview?: string;
  // New fields for stats and status updates
  total_channels?: number;
  total_developers?: number;
  total_jobs?: number;
  total_new_messages?: number;
  success_count?: number;
  error_count?: number;
  progress?: number;
  running?: boolean;
  account_id?: number;
  channels?: Array<{ id: number; username: string; is_listened: number; telegram_account_id: number | null }>;
}

const showJobNotification = (job: NewJobNotification) => {
  // Request notification permission if not granted
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
  }

  // Show notification if permission granted
  if ('Notification' in window && Notification.permission === 'granted') {
    const notification = new Notification(`New Job: ${job.title}`, {
      body: `${job.company} • ${job.channel}${job.is_remote ? ' • Remote' : ''}`,
      icon: '/favicon.ico',
      tag: `job-${job.job_id}`,
    });

    // Click notification to navigate to job detail
    notification.onclick = () => {
      window.location.href = `/jobs?jobId=${job.job_id}`;
      notification.close();
    };

    // Auto-close after 5 seconds
    setTimeout(() => notification.close(), 5000);
  }
};

export const useWebSocket = (url: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState<ProgressUpdate | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const connect = () => {
      try {
        ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as ProgressUpdate;
            setProgress(data);

            // Handle new job notification
            if (data.type === 'new_job' && data.new_job) {
              showJobNotification(data.new_job);
            }
          } catch (e) {
            // Silently ignore parse errors
          }
        };

        ws.onerror = () => {
          // Silently handle connection errors
          setIsConnected(false);
        };

        ws.onclose = () => {
          setIsConnected(false);
          // Attempt to reconnect after 5 seconds
          reconnectTimer = window.setTimeout(() => {
            connect();
          }, 5000);
        };
      } catch (e) {
        // Silently handle connection errors
        setIsConnected(false);
      }
    };

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, [url]);

  return { isConnected, progress };
};
