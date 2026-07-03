import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/services/api';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { ChevronDown } from 'lucide-react';

interface DailyJobsData {
  date: string;
  [channel: string]: number | string;
}

interface DailyJobsChartProps {
  days?: number;
}

export const DailyJobsChart = ({ days = 30 }: DailyJobsChartProps) => {
  const { t } = useTranslation();
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

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload || payload.length === 0) return null;
    return (
      <div
        className="bg-white/98 border border-gray-200 rounded-xl px-3 py-2.5 shadow-lg max-h-60 overflow-y-auto pointer-events-auto"
        onWheel={(e) => e.stopPropagation()}
      >
        <p className="text-xs font-semibold text-gray-800 mb-1.5">{label}</p>
        {payload.map((entry: any) => (
          <div key={entry.dataKey} className="flex items-center gap-2 text-xs py-0.5">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: entry.color }} />
            <span className="text-gray-600 truncate max-w-[140px]">{entry.dataKey}</span>
            <span className="font-semibold ml-auto text-gray-800">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  };

  if (loading) {
    return <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">{t('common.loading')}</div>;
  }

  if (data.length === 0) {
    return <div className="h-[260px] flex items-center justify-center text-sm text-muted-foreground">{t('common.noData')}</div>;
  }

  return (
    <div>
      {channels.length > 1 && (
        <div className="mb-3">
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm">
                <ChevronDown size={14} className="mr-2" />
                {t('dashboard.selectChannels')} ({channels.length - hiddenChannels.size} {t('dashboard.selected')})
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-56 p-3" align="start">
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {channels.map((channel, index) => {
                  const hidden = hiddenChannels.has(channel);
                  return (
                    <label key={channel} className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={!hidden}
                        onChange={() => toggleChannel(channel)}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span
                        className="text-sm"
                        style={{ color: colors[index % colors.length] }}
                      >
                        {channel}
                      </span>
                    </label>
                  );
                })}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      )}
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.5} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickFormatter={(value) => { const [,m,d] = value.split('-'); return `${new Date(0, parseInt(m)-1).toLocaleString('en-US',{month:'short'})} ${parseInt(d)}`; }}
            axisLine={{ stroke: '#e5e7eb' }}
            tickLine={false}
          />
          <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
          <Tooltip content={<CustomTooltip />} wrapperStyle={{ pointerEvents: 'auto' }} />
          {channels.map((channel, index) =>
            hiddenChannels.has(channel) ? null : (
              <Line
                key={channel}
                type="monotone"
                dataKey={channel}
                stroke={colors[index % colors.length]}
                strokeWidth={2}
                dot={{ r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            )
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
