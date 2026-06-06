import { useEffect, useRef, useState } from 'react';

export interface ProgressUpdate {
  type: 'fetch_start' | 'fetch_progress' | 'analyze_start' | 'analyze_progress' | 'analyze_complete' | 'error';
  channel?: string;
  channel_id?: number;
  status?: string;
  count?: number;
  total?: number;
  current?: number;
  analyzed?: number;
  processed?: number;
  jobs?: number;
  jobs_found?: number;
  developers?: number;
  developers_found?: number;
  error?: string;
}

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
