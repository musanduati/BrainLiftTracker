import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { Card, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { formatDate } from '../../utils/format';

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
  tweets?: Array<{
    id: number;
    content: string;
    thread_position: number;
    twitter_id?: string;
  }>;
}

interface FeedCardProps {
  item: FeedItem;
  onAccountClick?: (accountId: number) => void;
}

export const FeedCard: React.FC<FeedCardProps> = ({ item, onAccountClick }) => {
  const [expandedThread, setExpandedThread] = useState(false);

  const displayName = item.display_name || item.username;
  const isThread = item.type === 'thread';

  const handleAccountClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onAccountClick) {
      onAccountClick(item.account_id);
    }
  };

  const renderDOKBadge = () => {
    if (item.dok_type && item.change_type) {
      const isDOK3 = item.dok_type === 'DOK3';
      const isAdded = item.change_type === 'ADDED';
      
      const badgeColor = isDOK3 
        ? 'bg-gradient-to-r from-blue-100 to-blue-200 text-blue-800 dark:from-blue-900/30 dark:to-blue-800/30 dark:text-blue-300 border border-blue-200 dark:border-blue-700' 
        : 'bg-gradient-to-r from-purple-100 to-purple-200 text-purple-800 dark:from-purple-900/30 dark:to-purple-800/30 dark:text-purple-300 border border-purple-200 dark:border-purple-700';
      
      const changeIcon = isAdded ? '+' : '−';
      const changeColor = isAdded ? 'text-green-600' : 'text-red-600';
      
      return (
        <Badge className={`text-xs font-semibold ${badgeColor} shadow-sm h-4 px-1`}>
          <span className={`${changeColor} font-bold mr-0.5`}>{changeIcon}</span>
          {item.dok_type}
        </Badge>
      );
    }
    return null;
  };

  return (
    <Card className="overflow-hidden hover:shadow-sm transition-all duration-200 border border-border/50 mb-1.5">
      <CardContent className="p-2">
        <div className="flex gap-2">
          {/* Profile picture */}
          <div className="flex-shrink-0">
            <div 
              className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-xs font-bold cursor-pointer hover:scale-105 transition-transform shadow-sm ring-1 ring-black/5"
              onClick={handleAccountClick}
            >
              {item.profile_picture ? (
                <img
                  src={item.profile_picture}
                  alt={displayName}
                  className="w-6 h-6 rounded-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = 'none';
                    (e.target as HTMLImageElement).nextElementSibling?.setAttribute('style', 'display: flex');
                  }}
                />
              ) : null}
              <span className={item.profile_picture ? 'hidden' : ''}>
                {displayName?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
          </div>

          <div className="flex-1 min-w-0">
            {/* Header */}
            <div className="flex items-start justify-between gap-1 mb-0.5">
              <div className="flex items-center gap-1 flex-wrap">
                <h4 
                  className="text-xs font-medium cursor-pointer hover:underline truncate"
                  onClick={handleAccountClick}
                >
                  {displayName}
                </h4>
                <span className="text-muted-foreground text-xs">•</span>
                <span className="text-muted-foreground text-xs">
                  {formatDate(item.posted_at || item.created_at)}
                </span>
                {isThread && (
                  <Badge variant="secondary" className="text-xs px-1 py-0 h-4">
                    {item.tweet_count}
                  </Badge>
                )}
                {renderDOKBadge()}
              </div>

              <div className="flex items-center gap-1">
                {item.twitter_id && (
                  <a
                    href={`https://twitter.com/${item.username}/status/${item.twitter_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-0.5 rounded hover:bg-accent text-muted-foreground hover:text-foreground"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <ExternalLink size={10} />
                  </a>
                )}
              </div>
            </div>

            {/* Content */}
            <div className="space-y-1">
              {isThread ? (
                <>
                  {/* First tweet of thread */}
                  <p className="whitespace-pre-wrap break-words text-xs leading-tight">
                    {item.first_tweet || item.content}
                  </p>
                  
                  {/* Thread expansion */}
                  {item.tweets && item.tweets.length > 1 && (
                    <div>
                      <button
                        onClick={() => setExpandedThread(!expandedThread)}
                        className="flex items-center gap-0.5 text-xs text-blue-500 hover:text-blue-600 transition-colors px-1.5 py-0.5 rounded-full bg-blue-50 hover:bg-blue-100 dark:bg-blue-900/20 dark:hover:bg-blue-900/30"
                      >
                        {expandedThread ? (
                          <>
                            <ChevronUp size={10} />
                            Less
                          </>
                        ) : (
                          <>
                            <ChevronDown size={10} />
                            +{item.tweet_count! - 1}
                          </>
                        )}
                      </button>
                      
                      {expandedThread && (
                        <div className="mt-1 space-y-1 border-l border-blue-200 dark:border-blue-700 pl-1.5 bg-gradient-to-r from-blue-50/30 to-transparent dark:from-blue-900/5 rounded-r py-0.5">
                          {item.tweets.slice(1).map((tweet, index) => (
                            <div key={tweet.id} className="space-y-0.5">
                              <div className="flex items-center gap-0.5 text-xs font-medium text-blue-600 dark:text-blue-400 bg-blue-100 dark:bg-blue-900/30 rounded px-1 py-0 w-fit">
                                <span>{index + 2}</span>
                              </div>
                              <p className="whitespace-pre-wrap break-words text-xs leading-tight">
                                {tweet.content}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <p className="whitespace-pre-wrap break-words text-xs leading-tight">
                  {item.content}
                </p>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};