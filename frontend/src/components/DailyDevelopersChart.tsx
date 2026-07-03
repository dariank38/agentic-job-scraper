import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api from '@/services/api';

interface DailyDevelopersData {
  date: string;
  count: number;
}

interface DailyDevelopersChartProps {
  days?: number;
}

export const DailyDevelopersChart = ({ days = 30 }: DailyDevelopersChartProps) => {
  const { t } = useTranslation();
  const [data, setData] = useState<DailyDevelopersData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await api.getDailyDevelopersContacted(days);
        if (response.data) {
          // Convert {date: count} to [{date, count}]
          const chartData: DailyDevelopersData[] = Object.entries(response.data).map(([date, count]) => ({
            date,
            count: count as number,
          }));
          
          // Sort by date
          chartData.sort((a, b) => a.date.localeCompare(b.date));
          
          setData(chartData);
        }
      } catch (error) {
        console.error('Failed to fetch daily developers data:', error);
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
          <linearGradient id="devGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.9} />
            <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.5} />
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
          cursor={{ fill: 'rgba(139, 92, 246, 0.05)' }}
        />
        <Bar dataKey="count" fill="url(#devGradient)" radius={[6, 6, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  );
};
