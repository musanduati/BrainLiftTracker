import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';
import { Trophy, TrendingUp, Users } from 'lucide-react';
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
  threadCount?: number;
  totalActivity?: number;
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

  // Calculate total changes to get percentages
  const totalChanges = rankings.reduce((sum, user) => sum + (user.totalActivity || user.tweetCount), 0);

  // Prepare data for the chart with percentages
  const chartData = rankings.map(user => {
    const activityCount = user.totalActivity || user.tweetCount;
    return {
      name: user.username,
      tweets: user.tweetCount,
      threads: user.threadCount || 0,
      total: activityCount,
      percentage: totalChanges > 0 ? Math.round((activityCount / totalChanges) * 100) : 0,
      posted: user.postedCount,
      pending: user.pendingCount,
      failed: user.failedCount,
    };
  });

  // Use a gradient color scheme similar to the image
  const getBarColor = (index: number) => {
    const colors = [
      '#8B5CF6', // Purple
      '#A78BFA', // Light purple
      '#C4B5FD', // Lighter purple
      '#DDD6FE', // Very light purple
      '#E9D5FF', // Pale purple
    ];
    return colors[Math.min(index, colors.length - 1)];
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-background border rounded-lg shadow-lg p-3">
          <p className="font-semibold">{label}</p>
          <p className="text-sm text-muted-foreground">
            Total Activity: {data.total}
          </p>
          {data.tweets > 0 && (
            <p className="text-sm text-muted-foreground">Changes: {data.tweets}</p>
          )}
          {data.threads > 0 && (
            <p className="text-sm text-muted-foreground">Threads: {data.threads}</p>
          )}
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
          <Users size={20} className="text-purple-500" />
          User Activity Rankings
        </CardTitle>
        <CardDescription>Top users by total activity (changes and threads)</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Horizontal Bar Chart Container with Glass Effect */}
          <div className="p-6 rounded-xl bg-white/5 dark:bg-gray-900/20 backdrop-blur-sm border border-white/10 dark:border-gray-700/50 shadow-xl">
            <div className="space-y-3">
              {chartData.map((user, index) => {
                const percentage = user.percentage;
                const barColor = getBarColor(index);
                
                return (
                  <div key={index} className="space-y-1 group">
                    {/* Username and Percentage */}
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-sm font-medium truncate" title={user.name}>
                        {user.name}
                      </span>
                      <span className="text-sm font-semibold text-purple-600 dark:text-purple-400">
                        {percentage}%
                      </span>
                    </div>
                    
                    {/* Progress Bar with Hover Tooltip */}
                    <div className="relative w-full h-5 bg-gray-200/50 dark:bg-gray-800/50 rounded-full overflow-hidden backdrop-blur-sm">
                      <div
                        className="absolute top-0 left-0 h-full rounded-full transition-all duration-500 ease-out shadow-sm"
                        style={{
                          width: `${percentage}%`,
                          background: `linear-gradient(90deg, ${barColor} 0%, ${barColor}dd 100%)`,
                        }}
                      />
                      
                      {/* Hover Tooltip */}
                      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <span className="bg-gray-900/90 text-white text-xs px-2 py-1 rounded shadow-lg">
                          {user.threads > 0 ? `${user.total} total: ${user.tweets} changes, ${user.threads} threads` : `${user.total} changes`}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Summary Stats */}
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-purple-100/10 dark:bg-purple-900/10 backdrop-blur-sm border border-purple-200/20 dark:border-purple-700/20 text-center">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {rankings.length}
              </div>
              <div className="text-sm text-muted-foreground">Active Users</div>
            </div>
            <div className="p-4 rounded-lg bg-blue-100/10 dark:bg-blue-900/10 backdrop-blur-sm border border-blue-200/20 dark:border-blue-700/20 text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {totalChanges}
              </div>
              <div className="text-sm text-muted-foreground">Total Activity</div>
            </div>
            <div className="p-4 rounded-lg bg-green-100/10 dark:bg-green-900/10 backdrop-blur-sm border border-green-200/20 dark:border-green-700/20 text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {rankings.reduce((sum, user) => sum + user.postedCount, 0)}
              </div>
              <div className="text-sm text-muted-foreground">Posted</div>
            </div>
          </div>

        </div>
      </CardContent>
    </Card>
  );
};