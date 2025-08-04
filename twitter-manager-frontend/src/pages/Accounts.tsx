import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Grid3x3, List, RefreshCw, ArrowLeft } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { AccountCard } from '../components/accounts/AccountCard';
import { AccountList } from '../components/accounts/AccountList';
import { Button } from '../components/common/Button';
import { Skeleton } from '../components/common/Skeleton';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';

export const Accounts: React.FC = () => {
  const {
    accounts,
    accountViewMode,
    isLoadingAccounts,
    setAccounts,
    setAccountViewMode,
    setLoadingAccounts,
  } = useStore();

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setLoadingAccounts(true);
      const [accountsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);
      
      // Filter accounts to show those with either tweets or threads
      const accountsWithContent = accountsData
        .filter(account => {
          const hasTweets = tweetsData.some((tweet: any) => tweet.username === account.username);
          const hasThreads = threadsData.some((thread: any) => thread.account_username === account.username);
          return hasTweets || hasThreads;
        })
        .map(account => {
          // Count tweets for this account
          const accountTweetCount = tweetsData.filter(
            (tweet: any) => tweet.username === account.username
          ).length;
          
          // Count threads for this account
          const accountThreadCount = threadsData.filter(
            (thread: any) => thread.account_username === account.username
          ).length;
          
          return {
            ...account,
            tweetCount: accountTweetCount,
            threadCount: accountThreadCount
          };
        });
      
      setAccounts(accountsWithContent);
    } catch (error) {
      toast.error('Failed to load accounts');
      console.error('Load accounts error:', error);
    } finally {
      setLoadingAccounts(false);
    }
  };

  if (isLoadingAccounts) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Back Button */}
        <Link to="/" className="inline-flex mb-6">
          <Button variant="ghost" size="sm">
            <ArrowLeft size={16} className="mr-2" />
            Back to Dashboard
          </Button>
        </Link>

        {/* Header Actions */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-semibold">
            Twitter Accounts ({accounts.length})
          </h2>
          
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAccountViewMode(accountViewMode === 'grid' ? 'list' : 'grid')}
              title={accountViewMode === 'grid' ? 'Switch to list view' : 'Switch to grid view'}
            >
              {accountViewMode === 'grid' ? <List size={20} /> : <Grid3x3 size={20} />}
            </Button>
            
            <Button
              variant="secondary"
              size="sm"
              onClick={loadAccounts}
              disabled={isLoadingAccounts}
            >
              <RefreshCw size={16} className={`mr-2 ${isLoadingAccounts ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Account Grid/List */}
        {accounts.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No accounts with tweets found</p>
          </div>
        ) : accountViewMode === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {accounts.map((account) => (
              <AccountCard
                key={account.id}
                account={account}
              />
            ))}
          </div>
        ) : (
          <AccountList accounts={accounts} />
        )}
      </div>
    </>
  );
};