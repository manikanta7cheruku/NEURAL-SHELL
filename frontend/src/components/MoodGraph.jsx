import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import api from '../api';

export default function MoodGraph() {
  const [data, setData] = useState([]);
  const [current, setCurrent] = useState({ value: 0, label: 'neutral' });

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await api.get('/mood');
        setCurrent({ value: res.data.mood_value, label: res.data.label });
        const changes = res.data.recent_changes || [];
        const points = changes.map((c, i) => ({ i: i + 1, v: c.new_mood }));
        points.push({ i: points.length + 1, v: res.data.mood_value });
        setData(points);
      } catch {}
    };
    fetch();
  }, []);

  const moodColors = {
    frustrated: '#ef4444', down: '#f97316', slightly_off: '#eab308',
    neutral: '#6b7280', content: '#22c55e', happy: '#3b82f6', excited: '#a855f7'
  };

  if (data.length < 2) {
    return (
      <div className="flex items-center justify-center h-28 text-seven-text-muted text-xs">
        Mood tracking will appear after a few interactions
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-seven-text-muted">Mood Trend</span>
        <span
          className="text-xs font-medium px-2 py-0.5 rounded-full"
          style={{
            color: moodColors[current.label] || '#6b7280',
            backgroundColor: (moodColors[current.label] || '#6b7280') + '15',
          }}
        >
          {current.label} ({current.value >= 0 ? '+' : ''}{current.value.toFixed(2)})
        </span>
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={data}>
          <XAxis dataKey="i" hide />
          <YAxis domain={[-1, 1]} hide />
          <ReferenceLine y={0} stroke="#1a1a35" strokeDasharray="3 3" />
          <Tooltip
            contentStyle={{ background: '#111125', border: '1px solid #1a1a35', borderRadius: '8px', fontSize: '11px', color: '#94a3b8' }}
            formatter={(v) => [v.toFixed(2), 'Mood']}
            labelFormatter={() => ''}
          />
          <Line type="monotone" dataKey="v" stroke="#6366f1" strokeWidth={2} dot={{ fill: '#6366f1', r: 2, strokeWidth: 0 }} activeDot={{ r: 4, fill: '#818cf8' }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}