import React, { useState, useEffect } from 'react';
import { Users, ExternalLink, MoreVertical } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Skeleton } from '../common/Skeleton';
import { apiClient } from '../../services/api';
import { cn } from '../../utils/cn';

interface SavedFollower {
  twitter_user_id: string;
  username: string;
  display_name?: string;
  profile_picture?: string;
  verified?: boolean;
  is_approved?: boolean;
}

interface CompactFollowerListProps {
  accountId: number;
  limit?: number;
}

export const CompactFollowerList: React.FC<CompactFollowerListProps> = ({ accountId, limit = 8 }) => {
  const [followers, setFollowers] = useState<SavedFollower[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    const loadFollowers = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getSavedFollowers(accountId, 1, limit);
        setFollowers(data.followers || []);
        setTotalCount(data.pagination?.total || 0);
      } catch (error) {
        console.error('Error loading followers:', error);
        setFollowers([]);
        setTotalCount(0);
      } finally {
        setLoading(false);
      }
    };
    
    loadFollowers();
  }, [accountId, limit]);

  const getInitials = (name: string | undefined, username: string): string => {
    const displayName = name || username;
    if (!displayName) return '??';
    return displayName.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const getAvatarColor = (username: string): string => {
    const colors = [
      'from-blue-500 to-purple-600',
      'from-green-500 to-teal-600',
      'from-pink-500 to-rose-600',
      'from-orange-500 to-red-600',
      'from-indigo-500 to-blue-600',
      'from-purple-500 to-pink-600',
      'from-cyan-500 to-blue-600',
      'from-emerald-500 to-green-600',
    ];
    
    let hash = 0;
    for (let i = 0; i < username.length; i++) {
      hash = username.charCodeAt(i) + ((hash << 5) - hash);
    }
    
    return colors[Math.abs(hash) % colors.length];
  };

  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Users size={18} className="text-blue-500" />
            Followers
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-8" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (followers.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Users size={18} className="text-blue-500" />
            Followers
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-4">
            No followers yet
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users size={18} className="text-blue-500" />
            Followers
          </div>
          {totalCount > 0 && (
            <span className="text-xs text-muted-foreground font-normal">
              {totalCount} total
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {followers.map((follower, index) => (
            <div 
              key={follower.twitter_user_id || follower.username || `follower-${index}`} 
              className="flex items-center gap-2 p-2 rounded-lg hover:bg-muted/50 transition-colors group"
            >
              {/* Mini Profile Picture */}
              <div className="flex-shrink-0">
                {follower.profile_picture ? (
                  <img 
                    src={follower.profile_picture} 
                    alt={follower.username}
                    className="w-8 h-8 rounded-full object-cover"
                  />
                ) : (
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold bg-gradient-to-br",
                    getAvatarColor(follower.username)
                  )}>
                    {getInitials(follower.display_name, follower.username)}
                  </div>
                )}
              </div>

              {/* Username */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">
                  @{follower.username}
                </p>
              </div>

              {/* Action Icon */}
              <a 
                href={`https://twitter.com/${follower.username}`}
                target="_blank"
                rel="noopener noreferrer"
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-muted rounded"
              >
                <ExternalLink size={14} className="text-muted-foreground" />
              </a>
            </div>
          ))}
        </div>

        {totalCount > limit && (
          <div className="mt-3 pt-3 border-t">
            <button 
              className="text-xs text-blue-600 hover:text-blue-700 font-medium flex items-center gap-1 mx-auto"
              onClick={() => {
                // This could trigger showing the full follower modal or navigate somewhere
                const followerSection = document.querySelector('[data-follower-section]');
                followerSection?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              View all {totalCount} followers
              <MoreVertical size={12} />
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};