import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, TrendingUp, UserX } from 'lucide-react';
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

export const Dashboard: React.FC = () => {
  const { accounts, setAccounts, setTweets, setLoadingAccounts, setLoadingTweets } = useStore();
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


        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* User Activity Rankings */}
          <div className="lg:col-span-2">
            <UserActivityRankings />
          </div>

          {/* Inactive Accounts Section */}
          {inactiveAccounts.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <UserX size={20} className="text-orange-500" />
                      Inactive Accounts
                    </CardTitle>
                    <CardDescription>
                      {inactiveAccounts.length} account{inactiveAccounts.length !== 1 ? 's' : ''} with no changes
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {inactiveAccounts.slice(0, 5).map((account) => (
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
                {inactiveAccounts.length > 5 && (
                  <Link to="/accounts/inactive" className="block text-center mt-4">
                    <Button variant="secondary" size="sm">
                      View all {inactiveAccounts.length} inactive accounts
                    </Button>
                  </Link>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </>
  );
};