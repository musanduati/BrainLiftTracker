import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { List } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Skeleton } from '../common/Skeleton';
import { apiClient } from '../../services/api';
import toast from 'react-hot-toast';
import { getListGradient, getListShadow, initializeListColors } from '../../utils/listColors';

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
      
      // Initialize list colors based on sorted list IDs (ensures consistent colors)
      const sortedListIds = listRankings.map(list => list.id);
      initializeListColors(sortedListIds);
      
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

  // Use consistent list colors from the shared utility
  const getBarGradient = (listId: string) => {
    return getListGradient(listId);
  };
  
  // Get a complementary shadow color for the list
  const getBarShadow = (listId: string) => {
    return getListShadow(listId);
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <List size={20} className="text-green-500" />
            Org/Function Activity Rankings
          </CardTitle>
          <CardDescription>Activity levels across all groups</CardDescription>
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
            Org/Function Activity Rankings
          </CardTitle>
          <CardDescription>Activity levels across all groups</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            No group data available
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
          Org/Function Activity Rankings
        </CardTitle>
        <CardDescription>Activity distribution across {rankings.length} groups</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Horizontal Bar Chart Container with Glass Effect */}
          <div className="p-6 rounded-xl bg-white/5 dark:bg-gray-900/20 backdrop-blur-sm border border-white/10 dark:border-gray-700/50 shadow-xl">
            <div className="space-y-3">
              {rankings.slice(0, 10).map((list) => {
                const percentage = totalActivity > 0 
                  ? Math.round((list.totalActivity / totalActivity) * 100) 
                  : 0;
                // Ensure minimum 3% width for visual consistency, even for 0% activity
                const displayWidth = Math.max(percentage, list.totalActivity === 0 ? 3 : percentage);
                const barGradient = getBarGradient(list.id);
                const barShadow = getBarShadow(list.id);
                
                return (
                  <div 
                    key={list.id} 
                    className="space-y-1.5 group cursor-pointer transition-all duration-300 hover:scale-[1.02]"
                    onClick={() => navigate(`/lists/${list.id}`)}
                    title={`View brainlifts of ${list.name}`}
                  >
                    {/* List name and stats */}
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <span className="text-sm font-semibold truncate group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-purple-600 group-hover:to-pink-600 transition-all duration-300">
                          {list.name}
                        </span>
                        <span className="text-xs text-muted-foreground/70 group-hover:text-muted-foreground transition-colors">
                          ({list.activeMembers}/{list.memberCount} active)
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                          {percentage}%
                        </span>
                        {list.totalActivity === 0 && (
                          <span className="text-xs text-muted-foreground/60 italic">
                            inactive
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Enhanced Progress Bar */}
                    <div className="relative w-full h-6 bg-gradient-to-r from-gray-200/30 to-gray-200/50 dark:from-gray-800/30 dark:to-gray-800/50 rounded-full overflow-hidden backdrop-blur-sm group-hover:from-gray-200/50 group-hover:to-gray-200/70 dark:group-hover:from-gray-800/50 dark:group-hover:to-gray-800/70 transition-all duration-300">
                      {/* Animated gradient bar */}
                      <div
                        className="absolute top-0 left-0 h-full rounded-full transition-all duration-700 ease-out"
                        style={{
                          width: `${displayWidth}%`,
                          background: barGradient,
                          boxShadow: `0 2px 10px ${barShadow}, inset 0 1px 0 rgba(255,255,255,0.3)`,
                          opacity: list.totalActivity === 0 ? 0.6 : 1, // Slightly transparent for 0% lists
                        }}
                      >
                        {/* Shimmer effect */}
                        <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
                          <div className="h-full w-full bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
                        </div>
                      </div>
                      
                      {/* Percentage label inside bar (if wide enough) */}
                      {percentage > 15 && (
                        <div className="absolute left-2 top-1/2 -translate-y-1/2 text-white text-xs font-semibold drop-shadow-lg">
                          {percentage}%
                        </div>
                      )}
                      
                      {/* Hover Tooltip */}
                      <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
                        <span className="bg-gray-900/95 text-white text-xs px-3 py-1.5 rounded-lg shadow-xl backdrop-blur-sm">
                          {list.totalActivity} total activity • {list.activityRate}% brainlift activity rate
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
              <div className="text-sm text-muted-foreground">Total Brainlifts</div>
            </div>
            <div className="p-4 rounded-lg bg-purple-100/10 dark:bg-purple-900/10 backdrop-blur-sm border border-purple-200/20 dark:border-purple-700/20 text-center">
              <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                {Math.round(rankings.reduce((sum, list) => sum + list.activityRate, 0) / rankings.length)}%
              </div>
              <div className="text-sm text-muted-foreground">Avg Activity Rate</div>
            </div>
          </div>

          {/* View Groups Button */}
          <div className="mt-6 text-center">
            <Link to="/lists">
              <Button 
                variant="primary" 
                size="md"
                className="bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white shadow-lg hover:shadow-xl transition-all duration-200"
              >
                <List size={18} className="mr-2" />
                View All Groups
              </Button>
            </Link>
          </div>

        </div>
      </CardContent>
    </Card>
  );
};