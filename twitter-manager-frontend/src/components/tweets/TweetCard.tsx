import React from 'react';
import { Heart, MessageCircle, Repeat2, Eye, Copy, RefreshCw, Trash2, MoreVertical } from 'lucide-react';
import { Tweet, TwitterAccount } from '../../types';
import { Card, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { formatDate, formatNumber, getTweetStatusBadgeClass } from '../../utils/format';
import { cn } from '../../utils/cn';
import toast from 'react-hot-toast';

interface TweetCardProps {
  tweet: Tweet;
  account?: TwitterAccount;
  onRetry?: (tweet: Tweet) => void;
  onDelete?: (tweet: Tweet) => void;
}

export const TweetCard: React.FC<TweetCardProps> = ({
  tweet,
  account,
  onRetry,
  onDelete,
}) => {
  const handleCopyText = () => {
    navigator.clipboard.writeText(tweet.content);
    toast.success('Tweet copied to clipboard');
  };

  return (
    <Card className="overflow-hidden hover:bg-accent/30 transition-colors">
      <CardContent className="p-4">
        <div className="flex gap-3">
          {/* Profile picture */}
          {account && (
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
              {account.displayName?.[0] || account.username[0]}
            </div>
          )}

          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 flex-wrap">
                {account && (
                  <>
                    <h4 className="font-semibold">{account.displayName || account.username}</h4>
                    <span className="text-muted-foreground">@{account.username}</span>
                  </>
                )}
                <span className="text-muted-foreground">•</span>
                <span className="text-muted-foreground text-sm">
                  {formatDate(tweet.postedAt || tweet.createdAt)}
                </span>
                <Badge className={cn('ml-2', getTweetStatusBadgeClass(tweet.status))}>
                  {tweet.status}
                </Badge>
              </div>

              <button className="p-1 rounded-lg hover:bg-accent">
                <MoreVertical size={16} />
              </button>
            </div>

            {/* Content */}
            <p className="mt-2 whitespace-pre-wrap break-words">{tweet.content}</p>

            {/* Error message */}
            {tweet.error && (
              <div className="mt-2 p-2 rounded-md bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm">
                {tweet.error}
              </div>
            )}

            {/* Engagement metrics */}
            {tweet.engagementMetrics && tweet.status === 'posted' && (
              <div className="flex items-center gap-4 mt-3 text-sm text-muted-foreground">
                <button className="flex items-center gap-1 hover:text-red-500 transition-colors">
                  <Heart size={16} />
                  <span>{formatNumber(tweet.engagementMetrics.likes)}</span>
                </button>
                <button className="flex items-center gap-1 hover:text-green-500 transition-colors">
                  <Repeat2 size={16} />
                  <span>{formatNumber(tweet.engagementMetrics.retweets)}</span>
                </button>
                <button className="flex items-center gap-1 hover:text-blue-500 transition-colors">
                  <MessageCircle size={16} />
                  <span>{formatNumber(tweet.engagementMetrics.replies)}</span>
                </button>
                <div className="flex items-center gap-1">
                  <Eye size={16} />
                  <span>{formatNumber(tweet.engagementMetrics.views)}</span>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 mt-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopyText}
              >
                <Copy size={14} className="mr-1" />
                Copy
              </Button>

              {tweet.status === 'failed' && onRetry && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onRetry(tweet)}
                >
                  <RefreshCw size={14} className="mr-1" />
                  Retry
                </Button>
              )}

              {onDelete && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDelete(tweet)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 size={14} className="mr-1" />
                  Delete
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};