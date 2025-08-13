import React, { useState, useEffect } from 'react';
import { Users, UserCheck, UserX, ChevronLeft, ChevronRight, Search, ExternalLink, Shield, BarChart, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { Skeleton } from '../common/Skeleton';
import { apiClient } from '../../services/api';
import toast from 'react-hot-toast';
import { formatDistanceToNow } from 'date-fns';

interface SavedFollower {
  twitter_user_id: string;
  username: string;
  display_name: string;
  profile_picture?: string;
  description?: string;
  verified: boolean;
  followers_count: number;
  following_count: number;
  tweet_count: number;
  created_at: string;
  is_approved: boolean;
  name: string;
  approved_at: string;
  last_updated: string;
  status: string;
}

interface FollowerListProps {
  accountId: number;
  accountUsername: string;
}

export const FollowerList: React.FC<FollowerListProps> = ({ accountId, accountUsername }) => {
  const [followers, setFollowers] = useState<SavedFollower[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterVerified, setFilterVerified] = useState<boolean | null>(null);
  const [filterApproved, setFilterApproved] = useState<boolean | null>(null);
  const [sortBy, setSortBy] = useState<'followers' | 'recent' | 'tweets'>('followers');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const loadSavedFollowers = async () => {
      try {
        setLoading(true);
        const data = await apiClient.getSavedFollowers(accountId, currentPage, 20);
        
        setFollowers(data.followers || []);
        setTotalCount(data.pagination?.total || 0);
        setTotalPages(data.pagination?.pages || 1);
      } catch (error: any) {
        toast.error('Failed to load followers');
        console.error('Error loading followers:', error);
        setFollowers([]);
        setTotalCount(0);
        setTotalPages(1);
      } finally {
        setLoading(false);
      }
    };
    
    loadSavedFollowers();
  }, [accountId, currentPage]);

  const loadSavedFollowers = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getSavedFollowers(accountId, currentPage, 20);
      
      setFollowers(data.followers || []);
      setTotalCount(data.pagination?.total || 0);
      setTotalPages(data.pagination?.pages || 1);
    } catch (error: any) {
      toast.error('Failed to load followers');
      console.error('Error loading followers:', error);
      setFollowers([]);
      setTotalCount(0);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadSavedFollowers();
    setRefreshing(false);
    toast.success('Followers refreshed');
  };

  const handleApproveFollower = async (follower: SavedFollower) => {
    try {
      await apiClient.saveSingleFollower(accountId, {
        ...follower,
        is_approved: true
      });
      
      setFollowers(prev => prev.map(f => 
        f.twitter_user_id === follower.twitter_user_id 
          ? { ...f, is_approved: true }
          : f
      ));
      toast.success(`Approved ${follower.display_name || follower.username}`);
    } catch (error) {
      toast.error('Failed to approve follower');
      console.error('Error approving follower:', error);
    }
  };

  const handleUnapproveFollower = async (follower: SavedFollower) => {
    try {
      await apiClient.saveSingleFollower(accountId, {
        ...follower,
        is_approved: false
      });
      
      setFollowers(prev => prev.map(f => 
        f.twitter_user_id === follower.twitter_user_id 
          ? { ...f, is_approved: false }
          : f
      ));
      toast.success(`Unapproved ${follower.display_name || follower.username}`);
    } catch (error) {
      toast.error('Failed to unapprove follower');
      console.error('Error unapproving follower:', error);
    }
  };

  const handleRemoveFollower = async (followerId: string) => {
    try {
      await apiClient.removeSavedFollower(accountId, followerId);
      setFollowers(prev => prev.filter(f => f.twitter_user_id !== followerId));
      setTotalCount(prev => prev - 1);
      toast.success('Removed follower');
    } catch (error) {
      toast.error('Failed to remove follower');
      console.error('Error removing follower:', error);
    }
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(prev => prev + 1);
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(prev => prev - 1);
    }
  };

  const formatNumber = (num: number | undefined | null): string => {
    if (!num && num !== 0) return '0';
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
    return num.toString();
  };

  const getInitials = (name: string | undefined): string => {
    if (!name) return '??';
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const filteredFollowers = followers
    .filter(follower => {
      if (searchTerm) {
        const nameMatch = follower.display_name?.toLowerCase().includes(searchTerm.toLowerCase()) || false;
        const usernameMatch = follower.username?.toLowerCase().includes(searchTerm.toLowerCase()) || false;
        if (!nameMatch && !usernameMatch) {
          return false;
        }
      }
      if (filterVerified !== null && follower.verified !== filterVerified) {
        return false;
      }
      if (filterApproved !== null && follower.is_approved !== filterApproved) {
        return false;
      }
      return true;
    })
    .sort((a, b) => {
      switch (sortBy) {
        case 'followers':
          return (b.followers_count || 0) - (a.followers_count || 0);
        case 'tweets':
          return (b.tweet_count || 0) - (a.tweet_count || 0);
        case 'recent':
          const dateB = b.approved_at ? new Date(b.approved_at).getTime() : 0;
          const dateA = a.approved_at ? new Date(a.approved_at).getTime() : 0;
          return dateB - dateA;
        default:
          return 0;
      }
    });

  const renderFollowerCard = (follower: SavedFollower) => {
    const engagementScore = Math.min(100, Math.round(((follower.followers_count || 0) / 1000) + ((follower.tweet_count || 0) / 100)));
    
    return (
      <Card key={follower.twitter_user_id} className="overflow-hidden hover:shadow-xl transition-all duration-200 group border-0 bg-gradient-to-br from-background to-muted/20">
        {/* Engagement Score Bar */}
        <div className="h-1 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500" style={{width: `${engagementScore}%`}} />
        
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            {/* Profile Picture */}
            <div className="relative">
              {follower.profile_picture ? (
                <img 
                  src={follower.profile_picture} 
                  alt={follower.display_name || follower.username}
                  className="w-14 h-14 rounded-full object-cover ring-2 ring-background shadow-md"
                />
              ) : (
                <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold shadow-md">
                  {getInitials(follower.display_name || follower.username)}
                </div>
              )}
              {follower.verified && (
                <div className="absolute -bottom-1 -right-1 bg-background rounded-full p-0.5 shadow-lg">
                  <Shield size={16} className="text-blue-500 fill-blue-500" />
                </div>
              )}
            </div>

            {/* User Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="font-bold text-sm truncate">{follower.display_name || follower.username}</h4>
                    {follower.is_approved && (
                      <Badge variant="default" className="px-1.5 py-0 text-xs">
                        <UserCheck size={10} className="mr-0.5" />
                        Approved
                      </Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">@{follower.username}</p>
                </div>
                
                {/* Action Buttons */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <a 
                    href={`https://twitter.com/${follower.username}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-1.5 hover:bg-muted rounded-md transition-colors"
                  >
                    <ExternalLink size={14} className="text-muted-foreground" />
                  </a>
                  {follower.is_approved ? (
                    <button
                      onClick={() => handleUnapproveFollower(follower)}
                      className="p-1.5 hover:bg-orange-100 dark:hover:bg-orange-900/20 rounded-md transition-colors"
                      title="Unapprove"
                    >
                      <UserX size={14} className="text-orange-500" />
                    </button>
                  ) : (
                    <button
                      onClick={() => handleApproveFollower(follower)}
                      className="p-1.5 hover:bg-green-100 dark:hover:bg-green-900/20 rounded-md transition-colors"
                      title="Approve"
                    >
                      <UserCheck size={14} className="text-green-500" />
                    </button>
                  )}
                  <button
                    onClick={() => handleRemoveFollower(follower.twitter_user_id)}
                    className="p-1.5 hover:bg-red-100 dark:hover:bg-red-900/20 rounded-md transition-colors"
                    title="Remove"
                  >
                    <UserX size={14} className="text-red-500" />
                  </button>
                </div>
              </div>

              {/* Bio */}
              {follower.description && (
                <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                  {follower.description}
                </p>
              )}

              {/* Stats Grid */}
              <div className="grid grid-cols-3 gap-2 mt-3">
                <div className="text-center p-1.5 bg-muted/50 rounded">
                  <div className="text-xs font-bold text-foreground">{formatNumber(follower.followers_count)}</div>
                  <div className="text-[10px] text-muted-foreground">Followers</div>
                </div>
                <div className="text-center p-1.5 bg-muted/50 rounded">
                  <div className="text-xs font-bold text-foreground">{formatNumber(follower.tweet_count)}</div>
                  <div className="text-[10px] text-muted-foreground">Posts</div>
                </div>
                <div className="text-center p-1.5 bg-muted/50 rounded">
                  <div className="text-xs font-bold text-foreground">{formatNumber(follower.following_count)}</div>
                  <div className="text-[10px] text-muted-foreground">Following</div>
                </div>
              </div>

              {/* Status and Dates */}
              <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
                {follower.approved_at && (
                  <span>Added {formatDistanceToNow(new Date(follower.approved_at), { addSuffix: true })}</span>
                )}
                {follower.status && (
                  <Badge variant="outline" className="text-[10px] px-1 py-0">
                    {follower.status}
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderFollowerListItem = (follower: SavedFollower) => {
    return (
      <div key={follower.twitter_user_id} className="flex items-center gap-4 p-4 hover:bg-muted/50 transition-colors group">
        {/* Profile Picture */}
        <div className="relative flex-shrink-0">
          {follower.profile_picture ? (
            <img 
              src={follower.profile_picture} 
              alt={follower.display_name || follower.username}
              className="w-10 h-10 rounded-full object-cover"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-sm font-semibold">
              {getInitials(follower.display_name || follower.username)}
            </div>
          )}
        </div>

        {/* User Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium">{follower.display_name || follower.username}</span>
            {follower.verified && <Shield size={14} className="text-blue-500 fill-blue-500" />}
            {follower.is_approved && <UserCheck size={14} className="text-green-500" />}
          </div>
          <p className="text-sm text-muted-foreground">@{follower.username}</p>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span>{formatNumber(follower.followers_count)} followers</span>
          <span>{formatNumber(follower.tweet_count)} tweets</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <a 
            href={`https://twitter.com/${follower.username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-2 hover:bg-muted rounded-md transition-colors"
          >
            <ExternalLink size={16} className="text-muted-foreground" />
          </a>
          {follower.is_approved ? (
            <button
              onClick={() => handleUnapproveFollower(follower)}
              className="p-2 hover:bg-orange-100 dark:hover:bg-orange-900/20 rounded-md transition-colors"
            >
              <UserX size={16} className="text-orange-500" />
            </button>
          ) : (
            <button
              onClick={() => handleApproveFollower(follower)}
              className="p-2 hover:bg-green-100 dark:hover:bg-green-900/20 rounded-md transition-colors"
            >
              <UserCheck size={16} className="text-green-500" />
            </button>
          )}
          <button
            onClick={() => handleRemoveFollower(follower.twitter_user_id)}
            className="p-2 hover:bg-red-100 dark:hover:bg-red-900/20 rounded-md transition-colors"
          >
            <UserX size={16} className="text-red-500" />
          </button>
        </div>
      </div>
    );
  };

  if (loading && currentPage === 1) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users size={20} className="text-blue-500" />
            Saved Followers
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-0 shadow-lg">
      <CardHeader className="bg-muted/50 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <Users size={20} className="text-blue-500" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">Saved Followers</CardTitle>
              <p className="text-sm text-muted-foreground mt-0.5">
                {totalCount > 0 ? `${totalCount.toLocaleString()} saved followers for @${accountUsername}` : 'No saved followers yet'}
              </p>
            </div>
          </div>
          
          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={refreshing}
              className="px-3 py-1"
            >
              <RefreshCw size={14} className={`mr-1 ${refreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            
            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg">
              <Button
                variant={viewMode === 'grid' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('grid')}
                className="px-3 py-1"
              >
                Grid
              </Button>
              <Button
                variant={viewMode === 'list' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => setViewMode('list')}
                className="px-3 py-1"
              >
                List
              </Button>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-2 mt-4 pb-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by name or username..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-3 py-2 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
            />
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <BarChart size={16} className="text-muted-foreground" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="px-3 py-2 border border-input rounded-lg bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all"
            >
              <option value="followers">Most Followers</option>
              <option value="tweets">Most Active</option>
              <option value="recent">Recently Added</option>
            </select>
          </div>

          {/* Filter by Verification */}
          <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg">
            <Button
              variant={filterVerified === null ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilterVerified(null)}
              className="px-3 py-1"
            >
              All
            </Button>
            <Button
              variant={filterVerified === true ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilterVerified(true)}
              className="px-3 py-1"
            >
              <Shield size={12} className="mr-1" />
              Verified
            </Button>
            <Button
              variant={filterVerified === false ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilterVerified(false)}
              className="px-3 py-1"
            >
              Standard
            </Button>
          </div>

          {/* Filter by Approval */}
          <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-lg">
            <Button
              variant={filterApproved === null ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilterApproved(null)}
              className="px-3 py-1"
            >
              All
            </Button>
            <Button
              variant={filterApproved === true ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilterApproved(true)}
              className="px-3 py-1"
            >
              Approved
            </Button>
            <Button
              variant={filterApproved === false ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setFilterApproved(false)}
              className="px-3 py-1"
            >
              Pending
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {/* Quick Stats */}
        <div className="grid grid-cols-4 gap-3 mb-6 -mx-6 px-6 py-4 bg-muted/20">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {followers.filter(f => f.is_approved).length}
            </div>
            <div className="text-xs text-muted-foreground">Approved</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">
              {followers.filter(f => f.verified).length}
            </div>
            <div className="text-xs text-muted-foreground">Verified</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">
              {followers.filter(f => (f.followers_count || 0) > 10000).length}
            </div>
            <div className="text-xs text-muted-foreground">10K+ Followers</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-orange-600">
              {followers.length > 0 ? formatNumber(Math.round(followers.reduce((acc, f) => acc + (f.followers_count || 0), 0) / followers.length)) : '0'}
            </div>
            <div className="text-xs text-muted-foreground">Avg Followers</div>
          </div>
        </div>

        {filteredFollowers.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <Users size={48} className="mx-auto mb-3 opacity-20" />
            <p className="text-lg font-medium">
              {searchTerm || filterVerified !== null || filterApproved !== null 
                ? 'No followers match your filters' 
                : 'No saved followers yet'}
            </p>
            <p className="text-sm mt-1">
              {searchTerm || filterVerified !== null || filterApproved !== null
                ? 'Try adjusting your search criteria'
                : 'Saved followers will appear here once added'}
            </p>
          </div>
        ) : (
          <>
            {viewMode === 'grid' ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredFollowers.map(renderFollowerCard)}
              </div>
            ) : (
              <div className="divide-y divide-border rounded-lg border">
                {filteredFollowers.map(renderFollowerListItem)}
              </div>
            )}
          </>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-6">
            <Button
              variant="ghost"
              size="sm"
              onClick={handlePrevPage}
              disabled={currentPage === 1 || loading}
            >
              <ChevronLeft size={16} />
              Previous
            </Button>
            <span className="text-sm text-muted-foreground px-3">
              Page {currentPage} of {totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleNextPage}
              disabled={currentPage === totalPages || loading}
            >
              Next
              <ChevronRight size={16} />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
};