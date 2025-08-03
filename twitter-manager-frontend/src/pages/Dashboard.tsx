import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, MessageSquare, TrendingUp, AlertCircle, Plus } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import { formatNumber } from '../utils/format';
import toast from 'react-hot-toast';

export const Dashboard: React.FC = () => {
  const { accounts, tweets, setAccounts, setTweets, setLoadingAccounts, setLoadingTweets } = useStore();
  const [stats, setStats] = useState({
    totalAccounts: 0,
    healthyAccounts: 0,
    totalTweets: 0,
    pendingTweets: 0,
    failedTweets: 0,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoadingAccounts(true);
      setLoadingTweets(true);

      const [accountsData, tweetsData] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getTweets(),
      ]);

      setAccounts(accountsData);
      setTweets(tweetsData);

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
      description: `${stats.healthyAccounts} healthy`,
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
      link: '/tweets',
    },
    {
      title: 'Failed Tweets',
      value: stats.failedTweets,
      description: 'Need attention',
      icon: AlertCircle,
      color: 'text-red-500',
      bgColor: 'bg-red-100 dark:bg-red-900/20',
      link: '/tweets?status=failed',
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

  const recentActivity = [
    { type: 'tweet', message: 'New tweet posted by @johndoe', time: '2 minutes ago' },
    { type: 'account', message: 'Token refreshed for @janedoe', time: '15 minutes ago' },
    { type: 'error', message: 'Failed to post tweet for @company', time: '1 hour ago' },
    { type: 'tweet', message: 'Batch post completed: 5 tweets', time: '2 hours ago' },
  ];

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

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Activity */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent Activity</CardTitle>
                <CardDescription>Latest updates from your accounts</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {recentActivity.map((activity, index) => (
                    <div key={index} className="flex items-start gap-3">
                      <div className={`w-2 h-2 rounded-full mt-1.5 ${
                        activity.type === 'error' ? 'bg-red-500' :
                        activity.type === 'tweet' ? 'bg-green-500' : 'bg-blue-500'
                      }`} />
                      <div className="flex-1">
                        <p className="text-sm">{activity.message}</p>
                        <p className="text-xs text-muted-foreground mt-1">{activity.time}</p>
                      </div>
                    </div>
                  ))}
                </div>
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
      </div>
    </>
  );
};