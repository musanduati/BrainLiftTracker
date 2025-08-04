import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { Trophy, TrendingUp } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { apiClient } from '../../services/api';
import { getAvatarColor, getAvatarText } from '../../utils/avatar';
import toast from 'react-hot-toast';

interface UserRanking {
  rank: number;
  id: number;
  username: string;
  displayName: string;
  profilePicture: string;
  tweetCount: number;
  postedCount: number;
  pendingCount: number;
  failedCount: number;
}

export const UserActivityRankings: React.FC = () => {
  const [rankings, setRankings] = useState<UserRanking[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRankings();
  }, []);

  const loadRankings = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getUserActivityRankings();
      setRankings(data.rankings);
    } catch (error) {
      toast.error('Failed to load user rankings');
      console.error('Rankings error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Prepare data for the chart
  const chartData = rankings.map(user => ({
    name: `@${user.username}`,
    tweets: user.tweetCount,
    posted: user.postedCount,
    pending: user.pendingCount,
    failed: user.failedCount,
  }));

  // Colors for the bar chart
  const barColors = [
    '#3B82F6', // Blue
    '#10B981', // Green
    '#F59E0B', // Yellow
    '#8B5CF6', // Purple
    '#EF4444', // Red
    '#EC4899', // Pink
    '#6366F1', // Indigo
    '#14B8A6', // Teal
    '#F97316', // Orange
    '#84CC16', // Lime
  ];

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-background border rounded-lg shadow-lg p-3">
          <p className="font-semibold">{label}</p>
          <p className="text-sm text-muted-foreground">
            Total: {data.tweets} tweets
          </p>
          <p className="text-sm text-green-600">Posted: {data.posted}</p>
          <p className="text-sm text-yellow-600">Pending: {data.pending}</p>
          {data.failed > 0 && (
            <p className="text-sm text-red-600">Failed: {data.failed}</p>
          )}
        </div>
      );
    }
    return null;
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy size={20} className="text-yellow-500" />
            User Activity Rankings
          </CardTitle>
          <CardDescription>Top 10 users by tweet count</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (rankings.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy size={20} className="text-yellow-500" />
            User Activity Rankings
          </CardTitle>
          <CardDescription>Top 10 users by tweet count</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            No user activity data available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy size={20} className="text-yellow-500" />
          User Activity Rankings
        </CardTitle>
        <CardDescription>Top 10 users by tweet count</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* Bar Chart */}
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, bottom: 40, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis 
                  dataKey="name" 
                  angle={-45}
                  textAnchor="end"
                  height={60}
                  tick={{ fontSize: 12 }}
                  className="text-muted-foreground"
                />
                <YAxis 
                  tick={{ fontSize: 12 }}
                  className="text-muted-foreground"
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="tweets" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={barColors[index % barColors.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* User List */}
          <div className="space-y-3">
            {rankings.map((user) => {
              const rankIcon = user.rank === 1 ? '🥇' : user.rank === 2 ? '🥈' : user.rank === 3 ? '🥉' : null;
              
              return (
                <div 
                  key={user.id} 
                  className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  {/* Rank */}
                  <div className="text-lg font-bold w-8 text-center">
                    {rankIcon || `#${user.rank}`}
                  </div>

                  {/* Avatar */}
                  <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getAvatarColor(user.username)} flex items-center justify-center text-white font-semibold text-sm flex-shrink-0`}>
                    {getAvatarText(user.username, user.displayName)}
                  </div>

                  {/* User Info */}
                  <div className="min-w-0 flex-1">
                    <div className="font-medium truncate">{user.displayName || user.username}</div>
                    <div className="text-sm text-muted-foreground truncate">@{user.username}</div>
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-sm">
                    <div className="text-right">
                      <div className="font-semibold">{user.tweetCount}</div>
                      <div className="text-muted-foreground">tweets</div>
                    </div>
                    {user.postedCount > 0 && (
                      <div className="text-right text-green-600">
                        <div className="font-semibold">{user.postedCount}</div>
                        <div className="text-xs">posted</div>
                      </div>
                    )}
                    {user.pendingCount > 0 && (
                      <div className="text-right text-yellow-600">
                        <div className="font-semibold">{user.pendingCount}</div>
                        <div className="text-xs">pending</div>
                      </div>
                    )}
                  </div>

                  {/* Trend indicator */}
                  <TrendingUp size={16} className="text-green-500" />
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};