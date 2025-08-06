import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { List } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Skeleton } from '../common/Skeleton';
import { apiClient } from '../../services/api';
import toast from 'react-hot-toast';

interface ListRanking {
  id: string;
  name: string;
  memberCount: number;
  activeMembers: number;
  totalActivity: number;
  postedCount: number;
  pendingCount: number;
  failedCount: number;
  activityRate: number;
}

export const ListActivityRankings: React.FC = () => {
  const [rankings, setRankings] = useState<ListRanking[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadListRankings();
  }, []);

  const loadListRankings = async () => {
    try {
      setLoading(true);
      
      // Get lists with members and tweets data
      const [listsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      // Calculate activity for each list
      const listRankings: ListRanking[] = listsData.lists.map(list => {
        const members = list.members || [];
        const memberUsernames = members.map((m: any) => m.username);
        
        // Count tweets and threads for members in this list
        const listTweets = tweetsData.filter((tweet: any) => 
          memberUsernames.includes(tweet.username)
        );
        const listThreads = threadsData.filter((thread: any) => 
          memberUsernames.includes(thread.account_username)
        );
        
        // Calculate activity stats
        const totalActivity = listTweets.length + listThreads.length;
        const postedCount = listTweets.filter((t: any) => t.status === 'posted').length;
        const pendingCount = listTweets.filter((t: any) => t.status === 'pending').length;
        const failedCount = listTweets.filter((t: any) => t.status === 'failed').length;
        
        // Count active members (those with at least one tweet or thread)
        const activeMemberUsernames = new Set([
          ...listTweets.map((t: any) => t.username),
          ...listThreads.map((t: any) => t.account_username)
        ]);
        const activeMembers = activeMemberUsernames.size;
        const activityRate = members.length > 0 ? Math.round((activeMembers / members.length) * 100) : 0;
        
        return {
          id: list.id,
          name: list.name,
          memberCount: members.length,
          activeMembers,
          totalActivity,
          postedCount,
          pendingCount,
          failedCount,
          activityRate
        };
      });

      // Sort by total activity
      listRankings.sort((a, b) => b.totalActivity - a.totalActivity);
      
      setRankings(listRankings);
    } catch (error) {
      toast.error('Failed to load list rankings');
      console.error('List rankings error:', error);
    } finally {
      setLoading(false);
    }
  };

  // Calculate total activity to get percentages
  const totalActivity = rankings.reduce((sum, list) => sum + list.totalActivity, 0);

  // Use a gradient color scheme
  const getBarColor = (index: number) => {
    const colors = [
      '#10B981', // Green
      '#34D399', // Light green
      '#6EE7B7', // Lighter green
      '#A7F3D0', // Very light green
      '#D1FAE5', // Pale green
    ];
    return colors[Math.min(index, colors.length - 1)];
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <List size={20} className="text-green-500" />
            List Activity Rankings
          </CardTitle>
          <CardDescription>Activity levels across all lists</CardDescription>
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
            <List size={20} className="text-green-500" />
            List Activity Rankings
          </CardTitle>
          <CardDescription>Activity levels across all lists</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            No list data available
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <List size={20} className="text-green-500" />
          List Activity Rankings
        </CardTitle>
        <CardDescription>Activity distribution across {rankings.length} lists</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Horizontal Bar Chart Container with Glass Effect */}
          <div className="p-6 rounded-xl bg-white/5 dark:bg-gray-900/20 backdrop-blur-sm border border-white/10 dark:border-gray-700/50 shadow-xl">
            <div className="space-y-3">
              {rankings.slice(0, 10).map((list, index) => {
                const percentage = totalActivity > 0 
                  ? Math.round((list.totalActivity / totalActivity) * 100) 
                  : 0;
                const barColor = getBarColor(index);
                
                return (
                  <div 
                    key={list.id} 
                    className="space-y-1 group cursor-pointer transition-transform hover:scale-[1.02]"
                    onClick={() => navigate(`/lists/${list.id}`)}
                    title={`View members of ${list.name}`}
                  >
                    {/* List name and stats */}
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <span className="text-sm font-medium truncate group-hover:text-green-600 dark:group-hover:text-green-400 transition-colors">
                          {list.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          ({list.activeMembers}/{list.memberCount} active)
                        </span>
                      </div>
                      <span className="text-sm font-semibold text-green-600 dark:text-green-400">
                        {percentage}%
                      </span>
                    </div>
                    
                    {/* Progress Bar with Hover Tooltip */}
                    <div className="relative w-full h-5 bg-gray-200/50 dark:bg-gray-800/50 rounded-full overflow-hidden backdrop-blur-sm group-hover:bg-gray-200/70 dark:group-hover:bg-gray-800/70 transition-colors">
                      <div
                        className="absolute top-0 left-0 h-full rounded-full transition-all duration-500 ease-out shadow-sm group-hover:shadow-md"
                        style={{
                          width: `${percentage}%`,
                          background: `linear-gradient(90deg, ${barColor} 0%, ${barColor}dd 100%)`,
                        }}
                      />
                      
                      {/* Hover Tooltip */}
                      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                        <span className="bg-gray-900/90 text-white text-xs px-2 py-1 rounded shadow-lg">
                          {list.totalActivity} total activity ({list.activityRate}% member activity rate)
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
            <div className="p-4 rounded-lg bg-green-100/10 dark:bg-green-900/10 backdrop-blur-sm border border-green-200/20 dark:border-green-700/20 text-center">
              <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                {rankings.length}
              </div>
              <div className="text-sm text-muted-foreground">Total Lists</div>
            </div>
            <div className="p-4 rounded-lg bg-blue-100/10 dark:bg-blue-900/10 backdrop-blur-sm border border-blue-200/20 dark:border-blue-700/20 text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {rankings.reduce((sum, list) => sum + list.memberCount, 0)}
              </div>
              <div className="text-sm text-muted-foreground">Total Members</div>
            </div>
            <div className="p-4 rounded-lg bg-purple-100/10 dark:bg-purple-900/10 backdrop-blur-sm border border-purple-200/20 dark:border-purple-700/20 text-center">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {Math.round(rankings.reduce((sum, list) => sum + list.activityRate, 0) / rankings.length)}%
              </div>
              <div className="text-sm text-muted-foreground">Avg Activity Rate</div>
            </div>
          </div>

          {/* View Lists Button */}
          <div className="mt-6 text-center">
            <Link to="/lists">
              <Button 
                variant="primary" 
                size="md"
                className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
              >
                <List size={18} className="mr-2" />
                View All Lists
              </Button>
            </Link>
          </div>

        </div>
      </CardContent>
    </Card>
  );
};