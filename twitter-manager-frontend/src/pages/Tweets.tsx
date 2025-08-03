import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MessageSquare, Filter, RefreshCw } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { TweetCard } from '../components/tweets/TweetCard';
import { Button } from '../components/common/Button';
import { Skeleton } from '../components/common/Skeleton';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import { Tweet } from '../types';
import toast from 'react-hot-toast';

export const Tweets: React.FC = () => {
  const [searchParams] = useSearchParams();
  const accountId = searchParams.get('accountId');
  const statusFilter = searchParams.get('status');

  const {
    tweets,
    accounts,
    isLoadingTweets,
    setTweets,
    setLoadingTweets,
  } = useStore();

  const [filter, setFilter] = useState<'all' | 'pending' | 'posted' | 'failed'>('all');

  useEffect(() => {
    if (statusFilter) {
      setFilter(statusFilter as any);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadTweets();
  }, [accountId, filter]);

  const loadTweets = async () => {
    try {
      setLoadingTweets(true);
      const data = await apiClient.getTweets(
        accountId ? parseInt(accountId) : undefined,
        filter === 'all' ? undefined : filter
      );
      setTweets(data);
    } catch (error) {
      toast.error('Failed to load tweets');
      console.error('Load tweets error:', error);
    } finally {
      setLoadingTweets(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await apiClient.deleteTweet(id);
      await loadTweets();
      toast.success('Tweet deleted successfully');
    } catch (error) {
      toast.error('Failed to delete tweet');
      console.error('Delete tweet error:', error);
    }
  };

  const handleRepost = async (id: number) => {
    try {
      await apiClient.postTweet(id);
      await loadTweets();
      toast.success('Tweet posted successfully');
    } catch (error) {
      toast.error('Failed to post tweet');
      console.error('Post tweet error:', error);
    }
  };

  // Filter tweets based on the selected filter
  const filteredTweets = tweets.filter(tweet => {
    if (filter === 'all') return true;
    return tweet.status === filter;
  });

  const filterButtons = [
    { value: 'all', label: 'All Tweets' },
    { value: 'posted', label: 'Posted' },
    { value: 'pending', label: 'Pending' },
    { value: 'failed', label: 'Failed' },
  ];

  return (
    <>
      <TopBar title="Tweets" />
      
      <div className="p-6">
        {/* Header Actions */}
        <div className="flex flex-col sm:flex-row gap-4 mb-6">
          <div className="flex gap-2 flex-1">
            {filterButtons.map((btn) => (
              <Button
                key={btn.value}
                variant={filter === btn.value ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setFilter(btn.value as any)}
              >
                {btn.label}
              </Button>
            ))}
          </div>
          
          <div className="flex gap-2">
            <Button onClick={loadTweets} variant="secondary" size="sm">
              <RefreshCw size={16} className="mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Tweet List */}
        {isLoadingTweets ? (
          <div className="space-y-4">
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
            <Skeleton className="h-32" />
          </div>
        ) : filteredTweets.length === 0 ? (
          <div className="text-center py-12">
            <MessageSquare size={48} className="mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No tweets found</h3>
            <p className="text-muted-foreground mb-4">
              {filter === 'all' 
                ? "You haven't created any tweets yet." 
                : `No ${filter} tweets found.`}
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            <div className="text-sm text-muted-foreground mb-2">
              Showing {filteredTweets.length} tweet{filteredTweets.length !== 1 ? 's' : ''}
            </div>
            {filteredTweets.map((tweet) => (
              <TweetCard
                key={tweet.id}
                tweet={tweet}
                account={accounts.find(a => a.id === tweet.accountId)}
                onDelete={handleDelete}
                onRepost={handleRepost}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
};