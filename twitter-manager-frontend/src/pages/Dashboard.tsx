import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, TrendingUp, UserX, List } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import { formatNumber } from '../utils/format';
import toast from 'react-hot-toast';
import { getAvatarColor, getAvatarText } from '../utils/avatar';
import { TwitterAccount } from '../types';
import { UserActivityRankings } from '../components/dashboard/UserActivityRankings';
import { ListActivityRankings } from '../components/dashboard/ListActivityRankings';

export const Dashboard: React.FC = () => {
  const { accounts, setAccounts, setTweets, setLoadingAccounts, setLoadingTweets } = useStore();
  const [inactiveAccounts, setInactiveAccounts] = useState<TwitterAccount[]>([]);
  const [listsCount, setListsCount] = useState(0);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoadingAccounts(true);
      setLoadingTweets(true);

      const [accountsData, tweetsData, threadsData, listsData] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getTweets(),
        apiClient.getThreads(),
        apiClient.getLists()
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
      setListsCount(listsData.length);

    } catch (error) {
      toast.error('Failed to load dashboard data');
      console.error('Dashboard error:', error);
    } finally {
      setLoadingAccounts(false);
      setLoadingTweets(false);
    }
  };

  // Calculate activity rate - accounts with content vs total accounts
  const activeAccountsCount = accounts.length;
  const inactiveAccountsCount = inactiveAccounts.length;
  const totalAccountsCount = activeAccountsCount + inactiveAccountsCount;
  const activityRate = totalAccountsCount > 0 
    ? Math.round((activeAccountsCount / totalAccountsCount) * 100) 
    : 0;

  const statCards = [
    {
      title: 'Total Users Monitored',
      value: totalAccountsCount,
      description: 'All registered accounts',
      icon: Users,
      color: 'text-blue-500',
      bgColor: 'bg-blue-100 dark:bg-blue-900/20',
      link: '/accounts',
    },
    {
      title: 'Active Users',
      value: activeAccountsCount,
      description: 'Users with changes',
      icon: TrendingUp,
      color: 'text-green-500',
      bgColor: 'bg-green-100 dark:bg-green-900/20',
      link: '/accounts',
    },
    {
      title: 'Inactive Users',
      value: inactiveAccountsCount,
      description: 'No changes posted',
      icon: UserX,
      color: 'text-orange-500',
      bgColor: 'bg-orange-100 dark:bg-orange-900/20',
      link: '/accounts/inactive',
    },
    {
      title: 'Activity Rate',
      value: `${activityRate}%`,
      description: 'Percentage of active users',
      icon: TrendingUp,
      color: 'text-purple-500',
      bgColor: 'bg-purple-100 dark:bg-purple-900/20',
    },
  ];


  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {statCards.map((stat, index) => {
            const Icon = stat.icon;
            const CardComponent = (
              <Card className="hover:shadow-md transition-shadow cursor-pointer">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">{stat.title}</p>
                      <p className="text-2xl font-bold mt-1">
                        {typeof stat.value === 'string' ? stat.value : formatNumber(stat.value)}
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

            if (stat.link) {
              return (
                <Link key={index} to={stat.link}>
                  {CardComponent}
                </Link>
              );
            } else {
              return <div key={index}>{CardComponent}</div>;
            }
          })}
        </div>


        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* User Activity Rankings */}
          <UserActivityRankings />
          
          {/* List Activity Rankings */}
          <ListActivityRankings />
        </div>

      </div>
    </>
  );
};