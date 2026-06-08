import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/services/api';
import { Badge } from '@/components/ui/badge';

interface DailyJobsData {
  date: string;
  [channel: string]: number | string;
}

interface DailyJobsChartProps {
  days?: number;
}

export const DailyJobsChart = ({ days = 30 }: DailyJobsChartProps) => {
  const [data, setData] = useState<DailyJobsData[]>([]);
  const [loading, setLoading] = useState(true);
  const [channels, setChannels] = useState<string[]>([]);
  const [hiddenChannels, setHiddenChannels] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.getDailyJobs(days);
        if (response.data) {
          // Convert {date: {channel: count}} to [{date, channel1, channel2, ...}]
          const allChannels = new Set<string>();
          const chartData: DailyJobsData[] = [];
          
          Object.entries(response.data).forEach(([date, channelData]) => {
            const entry: DailyJobsData = { date };
            Object.entries(channelData as Record<string, number>).forEach(([channel, count]) => {
              allChannels.add(channel);
              entry[channel] = count;
            });
            chartData.push(entry);
          });
          
          // Sort by date
          chartData.sort((a, b) => a.date.localeCompare(b.date));
          
          setChannels(Array.from(allChannels));
          setData(chartData);
        }
      } catch (error) {
        console.error('Failed to fetch daily jobs data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [days]);

  const toggleChannel = (channel: string) => {
    setHiddenChannels(prev => {
      const next = new Set(prev);
      if (next.has(channel)) next.delete(channel);
      else next.add(channel);
      return next;
    });
  };

  // Generate colors for channels
  const colors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

  if (loading) {
    return <div className="h-64 flex items-center justify-center text-sm text-gray-500">Loading...</div>;
  }

  if (data.length === 0) {
    return <div className="h-64 flex items-center justify-center text-sm text-gray-500">No data available</div>;
  }

  return (
    <div>
      {channels.length > 1 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {channels.map((channel, index) => {
            const hidden = hiddenChannels.has(channel);
            return (
              <Badge
                key={channel}
                variant={hidden ? 'outline' : 'default'}
                className="cursor-pointer text-xs"
                style={!hidden ? { backgroundColor: colors[index % colors.length], border: 'none' } : { borderColor: colors[index % colors.length], color: colors[index % colors.length] }}
                onClick={() => toggleChannel(channel)}
              >
                {channel}
              </Badge>
            );
          })}
        </div>
      )}
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            tickFormatter={(value) => { const [,m,d] = value.split('-'); return `${new Date(0, parseInt(m)-1).toLocaleString('en-US',{month:'short'})} ${parseInt(d)}`; }}
          />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip
            labelFormatter={(value) => value}
            contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.95)', border: '1px solid #e5e7eb', borderRadius: '8px' }}
          />
          {channels.map((channel, index) =>
            hiddenChannels.has(channel) ? null : (
              <Line
                key={channel}
                type="monotone"
                dataKey={channel}
                stroke={colors[index % colors.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            )
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
