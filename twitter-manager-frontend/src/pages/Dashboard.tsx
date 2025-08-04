import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, MessageSquare, TrendingUp, AlertCircle, Plus, UserX } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import { formatNumber, formatRelativeTime } from '../utils/format';
import toast from 'react-hot-toast';
import { getAvatarColor, getAvatarText } from '../utils/avatar';
import { TwitterAccount } from '../types';
import { UserActivityRankings } from '../components/dashboard/UserActivityRankings';

export const Dashboard: React.FC = () => {
  const { accounts, tweets, setAccounts, setTweets, setLoadingAccounts, setLoadingTweets } = useStore();
  const [stats, setStats] = useState({
    totalAccounts: 0,
    healthyAccounts: 0,
    totalTweets: 0,
    pendingTweets: 0,
    failedTweets: 0,
  });
  const [inactiveAccounts, setInactiveAccounts] = useState<TwitterAccount[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoadingAccounts(true);
      setLoadingTweets(true);

      const [accountsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      // Filter accounts to only show those with tweets or threads
      const accountsWithContent = accountsData.filter(account => {
        const hasTweets = tweetsData.some((tweet: any) => tweet.username === account.username);
        const hasThreads = threadsData.some((thread: any) => thread.account_username === account.username);
        return hasTweets || hasThreads;
      });
      
      // Filter accounts without tweets or threads (inactive)
      const accountsWithoutContent = accountsData.filter(account => {
        const hasTweets = tweetsData.some((tweet: any) => tweet.username === account.username);
        const hasThreads = threadsData.some((thread: any) => thread.account_username === account.username);
        return !hasTweets && !hasThreads;
      });

      setAccounts(accountsWithContent);
      setTweets(tweetsData);
      setInactiveAccounts(accountsWithoutContent);

      // Calculate stats
      setStats({
        totalAccounts: accountsData.length,
        healthyAccounts: accountsData.filter(a => a.tokenStatus === 'healthy').length,
        totalTweets: tweetsData.length,
        pendingTweets: tweetsData.filter(t => t.status === 'pending').length,
        failedTweets: tweetsData.filter(t => t.status === 'failed').length,
      });
    } catch (error) {
      toast.error('Failed to load dashboard data');
      console.error('Dashboard error:', error);
    } finally {
      setLoadingAccounts(false);
      setLoadingTweets(false);
    }
  };

  const statCards = [
    {
      title: 'Total Accounts',
      value: stats.totalAccounts,
      description: `${accounts.length} active, ${inactiveAccounts.length} inactive`,
      icon: Users,
      color: 'text-blue-500',
      bgColor: 'bg-blue-100 dark:bg-blue-900/20',
      link: '/accounts',
    },
    {
      title: 'Total Tweets',
      value: stats.totalTweets,
      description: `${stats.pendingTweets} pending`,
      icon: MessageSquare,
      color: 'text-green-500',
      bgColor: 'bg-green-100 dark:bg-green-900/20',
    },
    {
      title: 'Failed Tweets',
      value: stats.failedTweets,
      description: 'Need attention',
      icon: AlertCircle,
      color: 'text-red-500',
      bgColor: 'bg-red-100 dark:bg-red-900/20',
    },
    {
      title: 'Engagement Rate',
      value: '2.4%',
      description: '+0.3% from last week',
      icon: TrendingUp,
      color: 'text-purple-500',
      bgColor: 'bg-purple-100 dark:bg-purple-900/20',
    },
  ];

  // Generate recent activity from posted tweets and threads
  const generateRecentActivity = () => {
    const activities = [];
    
    // Get posted tweets
    const postedTweets = tweets
      .filter(t => t.status === 'posted' && t.postedAt)
      .sort((a, b) => new Date(b.postedAt!).getTime() - new Date(a.postedAt!).getTime())
      .slice(0, 10)
      .map(tweet => ({
        type: 'tweet',
        message: `New tweet posted by @${tweet.username}`,
        time: formatRelativeTime(tweet.postedAt!)
      }));
    
    activities.push(...postedTweets);
    
    // Sort by most recent and take top 5
    return activities.slice(0, 5);
  };
  
  const recentActivity = generateRecentActivity();

  return (
    <>
      <TopBar title="Dashboard" />
      
      <div className="p-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {statCards.map((stat, index) => {
            const Icon = stat.icon;
            const content = (
              <Card key={index} className="hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">{stat.title}</p>
                      <p className="text-2xl font-bold mt-1">
                        {formatNumber(typeof stat.value === 'number' ? stat.value : 0) || stat.value}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">{stat.description}</p>
                    </div>
                    <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                      <Icon size={24} className={stat.color} />
                    </div>
                  </div>
                </CardContent>
              </Card>
            );

            return stat.link ? (
              <Link key={index} to={stat.link}>
                {content}
              </Link>
            ) : (
              content
            );
          })}
        </div>

        {/* Inactive Accounts Section */}
        {inactiveAccounts.length > 0 && (
          <div className="mb-8">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <UserX size={20} className="text-orange-500" />
                      Inactive Accounts
                    </CardTitle>
                    <CardDescription>
                      {inactiveAccounts.length} account{inactiveAccounts.length !== 1 ? 's' : ''} with no tweets
                    </CardDescription>
                  </div>
                  <Badge variant="secondary" className="text-orange-600">
                    Needs Attention
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {inactiveAccounts.slice(0, 6).map((account) => (
                    <div key={account.id} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                      <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-semibold text-sm`}>
                        {getAvatarText(account.username, account.displayName)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate">{account.displayName || account.username}</div>
                        <div className="text-sm text-muted-foreground truncate">@{account.username}</div>
                      </div>
                    </div>
                  ))}
                </div>
                {inactiveAccounts.length > 6 && (
                  <Link to="/accounts/inactive" className="block text-center mt-4">
                    <Button variant="outline" size="sm">
                      View all {inactiveAccounts.length} inactive accounts
                    </Button>
                  </Link>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent Posts</CardTitle>
                <CardDescription>Latest tweets posted by your accounts</CardDescription>
              </CardHeader>
              <CardContent>
                {recentActivity.length > 0 ? (
                  <div className="space-y-4">
                    {recentActivity.map((activity, index) => (
                      <div key={index} className="flex items-start gap-3">
                        <div className="w-2 h-2 rounded-full mt-1.5 bg-green-500" />
                        <div className="flex-1">
                          <p className="text-sm">{activity.message}</p>
                          <p className="text-xs text-muted-foreground mt-1">{activity.time}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    No recent posts to display
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Quick Actions</CardTitle>
              <CardDescription>Common tasks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Button className="w-full justify-start" variant="secondary">
                  <Plus size={16} className="mr-2" />
                  Add New Account
                </Button>
                <Button className="w-full justify-start" variant="secondary">
                  <Users size={16} className="mr-2" />
                  Refresh All Tokens
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* User Activity Rankings */}
        <div className="mt-6">
          <UserActivityRankings />
        </div>
      </div>
    </>
  );
};