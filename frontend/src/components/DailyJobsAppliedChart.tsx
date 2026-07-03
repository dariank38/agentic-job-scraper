import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/services/api';

interface DailyJobsAppliedData {
  date: string;
  count: number;
}

interface DailyJobsAppliedChartProps {
  days?: number;
}

export const DailyJobsAppliedChart = ({ days = 30 }: DailyJobsAppliedChartProps) => {
  const { t } = useTranslation();
  const [data, setData] = useState<DailyJobsAppliedData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.getDailyJobsApplied(days);
        if (response.data) {
          // Convert {date: count} to [{date, count}]
          const chartData: DailyJobsAppliedData[] = Object.entries(response.data).map(([date, count]) => ({
            date,
            count: count as number,
          }));
          
          // Sort by date
          chartData.sort((a, b) => a.date.localeCompare(b.date));
          
          setData(chartData);
        }
      } catch (error) {
        console.error('Failed to fetch daily jobs applied data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [days]);

  if (loading) {
    return <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">{t('common.loading')}</div>;
  }

  if (data.length === 0) {
    return <div className="h-[300px] flex items-center justify-center text-sm text-muted-foreground">{t('common.noData')}</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
        <defs>
          <linearGradient id="appliedGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f97316" stopOpacity={0.9} />
            <stop offset="100%" stopColor="#f97316" stopOpacity={0.5} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" opacity={0.5} />
        <XAxis 
          dataKey="date" 
          tick={{ fontSize: 11, fill: '#6b7280' }}
          tickFormatter={(value) => { const [,m,d] = value.split('-'); return `${new Date(0, parseInt(m)-1).toLocaleString('en-US',{month:'short'})} ${parseInt(d)}`; }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
        />
        <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
        <Tooltip 
          labelFormatter={(value) => value}
          contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.98)', border: '1px solid #e5e7eb', borderRadius: '10px', fontSize: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
          cursor={{ fill: 'rgba(249, 115, 22, 0.05)' }}
        />
        <Bar dataKey="count" fill="url(#appliedGradient)" radius={[6, 6, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  );
};
