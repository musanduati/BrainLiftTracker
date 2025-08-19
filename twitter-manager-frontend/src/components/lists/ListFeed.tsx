import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw, MessageSquare, ChevronDown, AlertCircle } from 'lucide-react';
import { Button } from '../common/Button';
import { Skeleton } from '../common/Skeleton';
import { FeedCard } from './FeedCard';
import { apiClient } from '../../services/api';
import toast from 'react-hot-toast';

interface FeedItem {
  id: string | number;
  type: 'tweet' | 'thread';
  account_id: number;
  username: string;
  display_name?: string;
  profile_picture?: string;
  content?: string;
  status?: string;
  created_at: string;
  posted_at?: string;
  twitter_id?: string;
  dok_type?: string;
  change_type?: string;
  // Thread specific
  thread_id?: string;
  tweet_count?: number;
  first_tweet?: string;
  tweets?: any[];
}

interface ListFeedProps {
  listId: number;
  listName: string;
  compact?: boolean; // Hide header for modal usage
}

const ITEMS_PER_PAGE = 20;

export const ListFeed: React.FC<ListFeedProps> = ({ listId, listName, compact = false }) => {
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const loadFeed = useCallback(async (offset: number = 0, append: boolean = false) => {
    try {
      if (offset === 0) {
        setLoading(true);
        setError(null);
      } else {
        setLoadingMore(true);
      }

      const response = await apiClient.getListFeed(listId, ITEMS_PER_PAGE, offset);
      
      if (append) {
        setFeed(prev => [...prev, ...response.feed]);
      } else {
        setFeed(response.feed);
      }
      
      setHasMore(response.has_more);
      setTotal(response.total);
    } catch (err) {
      const errorMessage = 'Failed to load feed';
      setError(errorMessage);
      toast.error(errorMessage);
      console.error('Load feed error:', err);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [listId]);

  useEffect(() => {
    loadFeed();
  }, [loadFeed]);

  const handleLoadMore = () => {
    if (!loadingMore && hasMore) {
      loadFeed(feed.length, true);
    }
  };

  const handleRefresh = () => {
    loadFeed();
  };

  const handleAccountClick = (accountId: number) => {
    navigate(`/accounts/${accountId}`);
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {!compact && (
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Recent Posts</h3>
            <Skeleton className="w-20 h-8" />
          </div>
        )}
        {compact && (
          <div className="flex justify-end mb-2">
            <Skeleton className="w-16 h-6" />
          </div>
        )}
        {[...Array(5)].map((_, i) => (
          <div key={i} className="border rounded-lg p-4">
            <div className="flex gap-3">
              <Skeleton className="w-12 h-12 rounded-full" />
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <Skeleton className="w-24 h-4" />
                  <Skeleton className="w-16 h-4" />
                  <Skeleton className="w-12 h-4" />
                </div>
                <Skeleton className="w-full h-4" />
                <Skeleton className="w-3/4 h-4" />
                <div className="flex gap-4 mt-3">
                  <Skeleton className="w-8 h-4" />
                  <Skeleton className="w-8 h-4" />
                  <Skeleton className="w-8 h-4" />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        {!compact && (
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">Recent Posts</h3>
            <Button variant="ghost" size="sm" onClick={handleRefresh}>
              <RefreshCw size={16} className="mr-2" />
              Retry
            </Button>
          </div>
        )}
        {compact && (
          <div className="flex justify-end mb-2">
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={handleRefresh}
              className="text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 p-2 text-xs"
            >
              <RefreshCw size={12} />
            </Button>
          </div>
        )}
        <div className="flex items-center justify-center py-12 text-center">
          <div>
            <AlertCircle size={48} className="mx-auto text-red-500 mb-4" />
            <p className="text-muted-foreground mb-4">{error}</p>
            <Button variant="secondary" onClick={handleRefresh}>
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${compact ? '' : 'space-y-4'}`}>
      {/* Header */}
      {!compact && (
        <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50/80 to-purple-50/80 dark:from-blue-900/20 dark:to-purple-900/20 rounded-lg border border-blue-100 dark:border-blue-800/50 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-sm">
              <MessageSquare size={20} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Recent Posts</h3>
              <p className="text-sm text-muted-foreground">
                {total} posts from <span className="font-medium text-blue-600 dark:text-blue-400">{listName}</span>
              </p>
            </div>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleRefresh} 
            disabled={loading}
            className="hover:bg-blue-100 dark:hover:bg-blue-900/30 text-blue-600 dark:text-blue-400"
          >
            <RefreshCw size={16} className={`mr-2 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      )}

      {/* Compact refresh button for modal */}
      {compact && (
        <div className="flex justify-end mb-2">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleRefresh} 
            disabled={loading}
            className="text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20 p-2 text-xs"
          >
            <RefreshCw size={12} className={`${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      )}

      {/* Feed */}
      {feed.length === 0 ? (
        <div className={`text-center ${compact ? 'py-8' : 'py-16'} bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900/50 dark:to-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-800`}>
          <div className="max-w-sm mx-auto">
            <div className={`${compact ? 'p-2' : 'p-4'} rounded-full bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 w-fit mx-auto ${compact ? 'mb-3' : 'mb-6'}`}>
              <MessageSquare size={compact ? 24 : 48} className="text-blue-500 dark:text-blue-400" />
            </div>
            <h4 className={`${compact ? 'text-base' : 'text-lg'} font-semibold text-gray-900 dark:text-gray-100 mb-2`}>No activity yet</h4>
            <p className={`text-muted-foreground ${compact ? 'text-sm' : ''}`}>
              Posts from brainlifts in <span className="font-medium text-blue-600 dark:text-blue-400">{listName}</span> will appear here
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-0">
          {feed.map((item) => (
            <FeedCard 
              key={`${item.type}-${item.id}`} 
              item={item} 
              onAccountClick={handleAccountClick}
            />
          ))}
          
          {/* Load More Button */}
          {hasMore && (
            <div className="flex justify-center pt-6 pb-4">
              <Button
                variant="secondary"
                onClick={handleLoadMore}
                disabled={loadingMore}
                className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border-blue-200 dark:border-blue-700 hover:from-blue-100 hover:to-purple-100 dark:hover:from-blue-900/30 dark:hover:to-purple-900/30 text-blue-700 dark:text-blue-300"
              >
                {loadingMore ? (
                  <RefreshCw size={16} className="mr-2 animate-spin" />
                ) : (
                  <ChevronDown size={16} className="mr-2" />
                )}
                {loadingMore ? 'Loading more posts...' : 'Load More Posts'}
              </Button>
            </div>
          )}
          
          {/* End indicator */}
          {!hasMore && feed.length > 0 && (
            <div className="text-center py-6 border-t border-gray-200 dark:border-gray-700">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 dark:bg-gray-800 text-sm text-muted-foreground">
                <div className="w-2 h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600"></div>
                You've reached the end of the feed
                <div className="w-2 h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600"></div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};