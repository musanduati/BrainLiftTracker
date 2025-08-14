import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trophy, Users } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { apiClient } from '../../services/api';
import toast from 'react-hot-toast';
import { getListGradient, getListShadow, initializeListColors } from '../../utils/listColors';

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
  listId?: string; // Track which list the user belongs to
}

interface UserActivityRankingsProps {
  onDataChange?: (data: { rankings: UserRanking[], totalChanges: number, selectedListId: string, listName?: string }) => void;
}

export const UserActivityRankings: React.FC<UserActivityRankingsProps> = ({ onDataChange }) => {
  const [allRankings, setAllRankings] = useState<UserRanking[]>([]);
  const [rankings, setRankings] = useState<UserRanking[]>([]);
  const [lists, setLists] = useState<any[]>([]);
  const [selectedListId, setSelectedListId] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    filterByList();
  }, [selectedListId, allRankings, lists]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [, listsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getUserActivityRankings(),
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);
      
      // Get ALL accounts with activity, not just top 10
      const accounts = await apiClient.getAccounts();
      
      // Initialize list colors based on list IDs
      const listIds = (listsData.lists || []).map((list: any) => list.id);
      initializeListColors(listIds);
      
      // Create a map of username to list ID for quick lookup
      const usernameToListId = new Map<string, string>();
      (listsData.lists || []).forEach((list: any) => {
        (list.members || []).forEach((member: any) => {
          usernameToListId.set(member.username, list.id);
        });
      });
      
      // Calculate activity for ALL brainlifts
      const allUsersWithActivity = accounts.map((account: any) => {
        const userTweets = tweetsData.filter((tweet: any) => tweet.username === account.username);
        const userThreads = threadsData.filter((thread: any) => thread.account_username === account.username);
        
        const tweetCount = userTweets.length;
        const threadCount = userThreads.length;
        const totalActivity = tweetCount + threadCount;
        const postedCount = userTweets.filter((t: any) => t.status === 'posted').length;
        const pendingCount = userTweets.filter((t: any) => t.status === 'pending').length;
        const failedCount = userTweets.filter((t: any) => t.status === 'failed').length;
        
        // Find which list this user belongs to
        const listId = usernameToListId.get(account.username);
        
        return {
          id: account.id,
          username: account.username,
          displayName: account.display_name || account.displayName || account.username,
          profilePicture: account.profile_picture || account.profilePicture,
          tweetCount,
          threadCount,
          totalActivity,
          postedCount,
          pendingCount,
          failedCount,
          rank: 0,
          listId
        };
      }).filter((user: any) => user.totalActivity > 0) // Only include brainlifts with activity
        .sort((a: any, b: any) => b.totalActivity - a.totalActivity); // Sort by activity
      
      // Add rank numbers
      allUsersWithActivity.forEach((user: any, index: number) => {
        user.rank = index + 1;
      });
      
      setAllRankings(allUsersWithActivity);
      setRankings(allUsersWithActivity.slice(0, 10)); // Show top 10 initially
      setLists(listsData.lists || []);
    } catch (error) {
      toast.error('Failed to load user rankings');
      console.error('Rankings error:', error);
      // Fallback to empty state
      setAllRankings([]);
      setRankings([]);
      setLists([]);
    } finally {
      setLoading(false);
    }
  };

  const filterByList = () => {
    if (selectedListId === 'all') {
      // Show top 10 from all brainlifts
      setRankings(allRankings.slice(0, 10));
    } else {
      // Filter by specific list - convert selectedListId to string for comparison
      const selectedList = lists.find(l => String(l.id) === String(selectedListId));
      
      if (selectedList && selectedList.members && selectedList.members.length > 0) {
        const memberUsernames = new Set((selectedList.members || []).map((m: any) => m.username));
        const filtered = allRankings.filter(user => memberUsernames.has(user.username));
        // Sort filtered results by activity to maintain ranking
        filtered.sort((a, b) => (b.totalActivity || b.tweetCount) - (a.totalActivity || a.tweetCount));
        // Take top 10 from the filtered list
        setRankings(filtered.slice(0, 10));
      } else {
        // List exists but has no members
        setRankings([]);
      }
    }
  };

  // Calculate total activity to get percentages
  const totalChanges = rankings.reduce((sum, user) => sum + (user.totalActivity || user.tweetCount), 0);

  // Prepare data for the chart with percentages
  const chartData = rankings.map(user => {
    const activityCount = user.totalActivity || user.tweetCount;
    return {
      name: user.displayName || user.username,
      tweets: user.tweetCount,
      threads: user.threadCount || 0,
      total: activityCount,
      percentage: totalChanges > 0 ? Math.round((activityCount / totalChanges) * 100) : 0,
      posted: user.postedCount,
      pending: user.pendingCount,
      failed: user.failedCount,
    };
  });

  // Use list-specific colors when showing filtered view, or default gradient for all
  const getBarGradient = (userRanking: UserRanking, index: number) => {
    if (userRanking.listId) {
      // User belongs to a list, use that list's color
      return getListGradient(userRanking.listId);
    }
    // Default gradient for users not in any list (shouldn't happen usually)
    const defaultGradients = [
      'linear-gradient(135deg, #8B5CF6 0%, #A78BFA 100%)', // Purple gradient
      'linear-gradient(135deg, #A78BFA 0%, #C4B5FD 100%)', // Light purple gradient
      'linear-gradient(135deg, #C4B5FD 0%, #DDD6FE 100%)', // Lighter purple gradient
      'linear-gradient(135deg, #DDD6FE 0%, #E9D5FF 100%)', // Very light purple gradient
      'linear-gradient(135deg, #E9D5FF 0%, #F3E7FC 100%)', // Pale purple gradient
    ];
    return defaultGradients[Math.min(index, defaultGradients.length - 1)];
  };
  
  const getBarShadow = (userRanking: UserRanking) => {
    if (userRanking.listId) {
      return getListShadow(userRanking.listId);
    }
    // Default shadow for users not in any list
    return 'rgba(139, 92, 246, 0.4)'; // Purple shadow
  };

  // Notify parent when data changes
  useEffect(() => {
    if (onDataChange) {
      const selectedList = lists.find(l => String(l.id) === String(selectedListId));
      onDataChange({
        rankings,
        totalChanges,
        selectedListId,
        listName: selectedList?.name
      });
    }
  }, [rankings, totalChanges, selectedListId, lists, onDataChange]);


  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy size={20} className="text-yellow-500" />
            Brainlift Activity Rankings
          </CardTitle>
          <CardDescription>Top 10 brainlifts by activity</CardDescription>
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

  if (rankings.length === 0 && !loading) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Trophy size={20} className="text-yellow-500" />
                Brainlift Activity Rankings
              </CardTitle>
              <CardDescription>
                {selectedListId === 'all' 
                  ? 'Top brainlifts by total activity' 
                  : `Top brainlifts in ${lists.find(l => l.id === selectedListId)?.name || 'list'}`
                }
              </CardDescription>
            </div>
            <select
              value={selectedListId}
              onChange={(e) => setSelectedListId(e.target.value)}
              className="px-3 py-1.5 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="all">All Brainlifts</option>
              {lists.length > 0 && (
                <optgroup label="Lists">
                  {lists.map((list) => (
                    <option key={list.id} value={list.id}>
                      {list.name} ({list.member_count || 0})
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            {selectedListId === 'all'
              ? 'No brainlift activity data available'
              : (() => {
                  const selectedList = lists.find(l => String(l.id) === String(selectedListId));
                  if (selectedList && selectedList.member_count === 0) {
                    return `The "${selectedList.name}" list has no members. Add accounts to this list to see their activity.`;
                  }
                  return `No activity found for members in ${selectedList?.name || 'this list'}`;
                })()
            }
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Users size={20} className="text-purple-500" />
              Brainlift Activity Rankings
            </CardTitle>
            <CardDescription>
              {selectedListId === 'all' 
                ? 'Top brainlifts by total activity (tweets and threads)' 
                : `Top users in ${lists.find(l => l.id === selectedListId)?.name || 'list'}`
              }
            </CardDescription>
          </div>
          <select
            value={selectedListId}
            onChange={(e) => setSelectedListId(e.target.value)}
            className="px-3 py-1.5 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="all">All Brainlifts</option>
            {lists.length > 0 && (
              <optgroup label="Lists">
                {lists.map((list) => (
                  <option key={list.id} value={list.id}>
                    {list.name} ({list.member_count || 0})
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Horizontal Bar Chart Container with Glass Effect */}
          <div className="p-6 rounded-xl bg-white/5 dark:bg-gray-900/20 backdrop-blur-sm border border-white/10 dark:border-gray-700/50 shadow-xl">
            <div className="space-y-3">
              {chartData.map((user, index) => {
                const percentage = user.percentage;
                const userRanking = rankings[index]; // Get the actual user from rankings
                const barGradient = getBarGradient(userRanking, index);
                const barShadow = getBarShadow(userRanking);
                
                return (
                  <div 
                    key={index} 
                    className="space-y-1 group cursor-pointer transition-transform hover:scale-[1.02]"
                    onClick={() => navigate(`/accounts/${userRanking.id}`)}
                    title={`View ${userRanking.displayName || userRanking.username}'s account details`}
                  >
                    {/* Username and Percentage */}
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <span className="text-sm font-medium truncate group-hover:text-transparent group-hover:bg-clip-text group-hover:bg-gradient-to-r group-hover:from-purple-600 group-hover:to-pink-600 transition-all duration-300">
                          {user.name}
                        </span>
                        {/* Show list name if user belongs to a list */}
                        {userRanking.listId && selectedListId === 'all' && (
                          <span className="text-xs text-muted-foreground/60">
                            ({lists.find((l: any) => String(l.id) === String(userRanking.listId))?.name})
                          </span>
                        )}
                      </div>
                      <span className="text-sm font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                        {percentage}%
                      </span>
                    </div>
                    
                    {/* Enhanced Progress Bar with List Color */}
                    <div className="relative w-full h-6 bg-gradient-to-r from-gray-200/30 to-gray-200/50 dark:from-gray-800/30 dark:to-gray-800/50 rounded-full overflow-hidden backdrop-blur-sm group-hover:from-gray-200/50 group-hover:to-gray-200/70 dark:group-hover:from-gray-800/50 dark:group-hover:to-gray-800/70 transition-all duration-300">
                      {/* Animated gradient bar */}
                      <div
                        className="absolute top-0 left-0 h-full rounded-full transition-all duration-700 ease-out"
                        style={{
                          width: `${percentage}%`,
                          background: barGradient,
                          boxShadow: `0 2px 10px ${barShadow}, inset 0 1px 0 rgba(255,255,255,0.3)`,
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
                          {user.threads > 0 ? `${user.total} total: ${user.tweets} tweets, ${user.threads} threads` : `${user.total} tweets`}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>


        </div>
      </CardContent>
    </Card>
  );
};