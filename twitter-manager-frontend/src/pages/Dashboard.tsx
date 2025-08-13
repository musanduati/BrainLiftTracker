import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Users, TrendingUp, UserX } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent } from '../components/common/Card';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import { formatNumber } from '../utils/format';
import toast from 'react-hot-toast';
import { TwitterAccount } from '../types';
import { UserActivityRankings } from '../components/dashboard/UserActivityRankings';
import { ListActivityRankings } from '../components/dashboard/ListActivityRankings';
import { UserActivityStats } from '../components/dashboard/UserActivityStats';

export const Dashboard: React.FC = () => {
  const { accounts, setAccounts, setTweets, setLoadingAccounts, setLoadingTweets } = useStore();
  const [inactiveAccounts, setInactiveAccounts] = useState<TwitterAccount[]>([]);
  const [userActivityData, setUserActivityData] = useState<{
    rankings: any[];
    totalChanges: number;
    selectedListId: string;
    listName?: string;
  }>({
    rankings: [],
    totalChanges: 0,
    selectedListId: 'all'
  });

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
      title: 'Total Brainlifts Monitored',
      value: totalAccountsCount,
      description: 'All registered accounts',
      icon: Users,
      color: 'text-blue-500',
      bgColor: 'bg-blue-100 dark:bg-blue-900/20',
      link: '/accounts',
    },
    {
      title: 'Active Brainlifts',
      value: activeAccountsCount,
      description: 'Brainlifts with tweets',
      icon: TrendingUp,
      color: 'text-green-500',
      bgColor: 'bg-green-100 dark:bg-green-900/20',
      link: '/accounts',
    },
    {
      title: 'Inactive Brainlifts',
      value: inactiveAccountsCount,
      description: 'No tweets posted',
      icon: UserX,
      color: 'text-orange-500',
      bgColor: 'bg-orange-100 dark:bg-orange-900/20',
      link: '/accounts/inactive',
    },
    {
      title: 'Activity Rate',
      value: `${activityRate}%`,
      description: 'Percentage of active brainlifts',
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
              <Card className="group relative overflow-hidden hover:shadow-xl transition-all duration-300 cursor-pointer hover:scale-[1.02] hover:-translate-y-1">
                <CardContent className="p-6 relative z-10">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">{stat.title}</p>
                      <p className="text-2xl font-bold mt-1 group-hover:scale-105 transition-transform origin-left">
                        {typeof stat.value === 'string' ? stat.value : formatNumber(stat.value)}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">{stat.description}</p>
                    </div>
                    <div className={`p-3 rounded-lg ${stat.bgColor} group-hover:scale-110 transition-transform duration-300`}>
                      <Icon size={24} className={`${stat.color} group-hover:animate-pulse`} />
                    </div>
                  </div>
                </CardContent>
                {/* Gradient overlay on hover */}
                <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
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
          {/* Left Column - Brainlift Activity Rankings */}
          <div>
            <UserActivityRankings onDataChange={setUserActivityData} />
          </div>
          
          {/* Right Column - List Activity Rankings and Brainlift Activity Stats */}
          <div className="space-y-6">
            <ListActivityRankings />
            <UserActivityStats 
              rankings={userActivityData.rankings}
              totalChanges={userActivityData.totalChanges}
              selectedListId={userActivityData.selectedListId}
              listName={userActivityData.listName}
            />
          </div>
        </div>

      </div>
    </>
  );
};