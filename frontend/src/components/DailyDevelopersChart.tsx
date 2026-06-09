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
    return <div className="h-64 flex items-center justify-center text-sm text-gray-500">{t('common.loading')}</div>;
  }

  if (data.length === 0) {
    return <div className="h-64 flex items-center justify-center text-sm text-gray-500">{t('common.noData')}</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
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
        <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
};
