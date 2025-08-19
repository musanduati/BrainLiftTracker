import React, { useEffect, useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, Users, Activity, ExternalLink, ChevronLeft, ChevronRight, TrendingUp, UserCheck, Clock, BarChart3, AlertCircle, MessageSquare, X } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { ListFeed } from '../components/lists/ListFeed';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';
import { formatNumber } from '../utils/format';

interface ListMember {
  id: number;
  username: string;
  displayName: string;
  profilePicture: string;
  tweetCount?: number;
  threadCount?: number;
  lastActivity?: string;
}

interface ListDetails {
  id: string;
  list_id: string;
  name: string;
  description: string;
  mode: string;
  owner_username: string;
  member_count: number;
  members: ListMember[];
}

const BRAINLIFTS_PER_PAGE = 30; // More brainlifts per page

export const ListMembers: React.FC = () => {
  const { listId } = useParams<{ listId: string }>();
  const navigate = useNavigate();
  const [list, setList] = useState<ListDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [showFeed, setShowFeed] = useState(false);
  const [feedAnimating, setFeedAnimating] = useState(false);

  useEffect(() => {
    loadListDetails();
  }, [listId]);

  const loadListDetails = async () => {
    try {
      setLoading(true);
      
      // Get lists data and find the specific list
      const [listsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      // Convert both to strings for comparison since URL params are always strings
      const currentList = listsData.lists.find((l: any) => String(l.id) === String(listId));
      
      if (!currentList) {
        toast.error(`List not found with ID: ${listId}`);
        navigate('/lists');
        return;
      }

      // Enhance member data with activity stats
      const enhancedMembers = (currentList.members || []).map((member: any) => {
        const memberTweets = tweetsData.filter((t: any) => t.username === member.username);
        const memberThreads = threadsData.filter((t: any) => t.account_username === member.username);
        
        let lastTweetDate = null;
        if (memberTweets.length > 0) {
          const validDates = memberTweets
            .map((t: any) => new Date(t.created_at))
            .filter((d: Date) => !isNaN(d.getTime()));
          if (validDates.length > 0) {
            lastTweetDate = new Date(Math.max(...validDates.map(d => d.getTime())));
          }
        }
        
        let lastThreadDate = null;
        if (memberThreads.length > 0) {
          const validDates = memberThreads
            .map((t: any) => new Date(t.created_at))
            .filter((d: Date) => !isNaN(d.getTime()));
          if (validDates.length > 0) {
            lastThreadDate = new Date(Math.max(...validDates.map(d => d.getTime())));
          }
        }
        
        let lastActivity = null;
        const validDates = [lastTweetDate, lastThreadDate].filter((d): d is Date => d !== null && !isNaN(d.getTime()));
        if (validDates.length > 0) {
          lastActivity = new Date(Math.max(...validDates.map(d => d.getTime()))).toISOString();
        }

        return {
          ...member,
          tweetCount: memberTweets.length,
          threadCount: memberThreads.length,
          lastActivity
        };
      });

      // Sort members by total activity (tweets + threads)
      enhancedMembers.sort((a: ListMember, b: ListMember) => 
        ((b.tweetCount || 0) + (b.threadCount || 0)) - ((a.tweetCount || 0) + (a.threadCount || 0))
      );

      setList({
        ...currentList,
        members: enhancedMembers
      });
    } catch (error) {
      toast.error('Failed to load list details');
      console.error('Load list details error:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMemberClick = (memberId: number) => {
    navigate(`/accounts/${memberId}`);
  };

  const openFeed = () => {
    setShowFeed(true);
    setTimeout(() => setFeedAnimating(true), 10);
  };

  const closeFeed = () => {
    setFeedAnimating(false);
    setTimeout(() => setShowFeed(false), 300);
  };

  // Keyboard support
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && showFeed) {
        closeFeed();
      }
    };

    if (showFeed) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [showFeed]);

  // Calculate paginated brainlifts
  const paginatedMembers = useMemo(() => {
    if (!list) return [];
    const startIndex = (currentPage - 1) * BRAINLIFTS_PER_PAGE;
    const endIndex = startIndex + BRAINLIFTS_PER_PAGE;
    return list.members.slice(startIndex, endIndex);
  }, [list, currentPage]);

  // Calculate total pages
  const totalPages = list ? Math.ceil(list.members.length / BRAINLIFTS_PER_PAGE) : 0;

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <Skeleton className="h-32 mb-6" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
            {[...Array(8)].map((_, i) => (
              <Skeleton key={i} className="h-32" />
            ))}
          </div>
        </div>
      </>
    );
  }

  if (!list) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">List not found</p>
            <Link to="/lists">
              <Button variant="primary">
                <ArrowLeft size={16} className="mr-2" />
                Back to Lists
              </Button>
            </Link>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <Link to="/lists" className="inline-flex mb-4">
            <Button variant="ghost" size="sm">
              <ArrowLeft size={16} className="mr-2" />
              Back to Lists
            </Button>
          </Link>

          <Card className="mb-6">
            <CardHeader>
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-2xl">{list.name}</CardTitle>
                  <CardDescription className="mt-2">
                    {list.description || 'No description'}
                  </CardDescription>
                </div>
                <Badge variant={list.mode === 'public' ? 'secondary' : 'default'}>
                  {list.mode}
                </Badge>
              </div>
              <div className="flex items-center gap-4 mt-4 text-sm text-muted-foreground">
                <span>Owner: @{list.owner_username}</span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Users size={14} />
                  {list.member_count} brainlifts
                </span>
              </div>
            </CardHeader>
          </Card>

          {/* Metrics Section */}
          {(() => {
            // Calculate metrics
            const activeMembers = list.members.filter(m => (m.tweetCount || 0) + (m.threadCount || 0) > 0);
            const activityRate = list.members.length > 0 ? Math.round((activeMembers.length / list.members.length) * 100) : 0;
            const totalTweets = list.members.reduce((sum, m) => sum + (m.tweetCount || 0), 0);
            const totalThreads = list.members.reduce((sum, m) => sum + (m.threadCount || 0), 0);
            const totalActivity = totalTweets + totalThreads;
            const avgActivityPerMember = activeMembers.length > 0 ? Math.round(totalActivity / activeMembers.length) : 0;
            
            // Find top performers
            const topPerformers = [...list.members]
              .sort((a, b) => ((b.tweetCount || 0) + (b.threadCount || 0)) - ((a.tweetCount || 0) + (a.threadCount || 0)))
              .slice(0, 3);
            
            // Calculate activity distribution
            const highActivity = activeMembers.filter(m => (m.tweetCount || 0) + (m.threadCount || 0) > avgActivityPerMember).length;
            const mediumActivity = activeMembers.filter(m => {
              const activity = (m.tweetCount || 0) + (m.threadCount || 0);
              return activity > 0 && activity <= avgActivityPerMember;
            }).length;
            const noActivity = list.members.length - activeMembers.length;
            
            // Recent activity
            const recentlyActive = list.members.filter(m => {
              if (!m.lastActivity) return false;
              const daysSinceActive = (Date.now() - new Date(m.lastActivity).getTime()) / (1000 * 60 * 60 * 24);
              return daysSinceActive <= 7;
            }).length;
            
            return (
              <div className="space-y-6 mb-6">
                {/* Key Metrics Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-muted-foreground">Activity Rate</p>
                          <p className="text-2xl font-bold mt-1">{activityRate}%</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {activeMembers.length} of {list.members.length} active
                          </p>
                        </div>
                        <div className={`p-3 rounded-lg ${activityRate >= 70 ? 'bg-green-100 dark:bg-green-900/20' : activityRate >= 40 ? 'bg-yellow-100 dark:bg-yellow-900/20' : 'bg-red-100 dark:bg-red-900/20'}`}>
                          <TrendingUp size={24} className={activityRate >= 70 ? 'text-green-500' : activityRate >= 40 ? 'text-yellow-500' : 'text-red-500'} />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-muted-foreground">Total Activity</p>
                          <p className="text-2xl font-bold mt-1">{formatNumber(totalActivity)}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {formatNumber(totalActivity)} posts
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-blue-100 dark:bg-blue-900/20">
                          <BarChart3 size={24} className="text-blue-500" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-muted-foreground">Avg per Active Brainlift</p>
                          <p className="text-2xl font-bold mt-1">{avgActivityPerMember}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            posts per brainlift
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-purple-100 dark:bg-purple-900/20">
                          <UserCheck size={24} className="text-purple-500" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  <Card>
                    <CardContent className="p-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-muted-foreground">Recently Active</p>
                          <p className="text-2xl font-bold mt-1">{recentlyActive}</p>
                          <p className="text-xs text-muted-foreground mt-1">
                            in last 7 days
                          </p>
                        </div>
                        <div className="p-3 rounded-lg bg-indigo-100 dark:bg-indigo-900/20">
                          <Clock size={24} className="text-indigo-500" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
                
                {/* Activity Distribution and Top Performers */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Activity Distribution */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">Activity Distribution</CardTitle>
                      <CardDescription>Member engagement levels</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm">High Activity</span>
                            <span className="text-sm font-medium">{highActivity} brainlifts</span>
                          </div>
                          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                            <div 
                              className="bg-green-500 h-2 rounded-full transition-all duration-500"
                              style={{ width: `${list.members.length > 0 ? (highActivity / list.members.length) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                        
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm">Medium Activity</span>
                            <span className="text-sm font-medium">{mediumActivity} brainlifts</span>
                          </div>
                          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                            <div 
                              className="bg-yellow-500 h-2 rounded-full transition-all duration-500"
                              style={{ width: `${list.members.length > 0 ? (mediumActivity / list.members.length) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                        
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm">No Activity</span>
                            <span className="text-sm font-medium">{noActivity} brainlifts</span>
                          </div>
                          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                            <div 
                              className="bg-red-500 h-2 rounded-full transition-all duration-500"
                              style={{ width: `${list.members.length > 0 ? (noActivity / list.members.length) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Top Performers */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg">Top Performers</CardTitle>
                      <CardDescription>Most active brainlifts in this Org/Function</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {topPerformers.length > 0 ? (
                          topPerformers.map((member, index) => {
                            const activity = (member.tweetCount || 0) + (member.threadCount || 0);
                            return (
                              <div 
                                key={member.id}
                                className="flex items-center gap-3 p-3 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
                                onClick={() => handleMemberClick(member.id)}
                              >
                                <div className="flex-shrink-0">
                                  <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-white
                                    ${index === 0 ? 'bg-gradient-to-br from-yellow-400 to-yellow-600' : 
                                      index === 1 ? 'bg-gradient-to-br from-gray-400 to-gray-600' : 
                                      'bg-gradient-to-br from-orange-400 to-orange-600'}`}>
                                    {index + 1}
                                  </div>
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium text-sm truncate">{member.displayName}</p>
                                  <p className="text-xs text-muted-foreground">@{member.username}</p>
                                </div>
                                <div className="text-right">
                                  <p className="text-sm font-bold">{activity}</p>
                                  <p className="text-xs text-muted-foreground">posts</p>
                                </div>
                              </div>
                            );
                          })
                        ) : (
                          <div className="text-center py-8 text-muted-foreground">
                            <AlertCircle size={24} className="mx-auto mb-2 opacity-50" />
                            <p className="text-sm">No activity yet</p>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            );
          })()}

        </div>

        {/* Floating Feed Button */}
        <div className="fixed top-20 right-6 z-30">
          <Button
            onClick={openFeed}
            className="bg-primary/90 hover:bg-primary text-primary-foreground shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 rounded-full p-3 backdrop-blur-sm border border-border/20 ring-1 ring-black/5 dark:ring-white/10"
            size="sm"
          >
            <MessageSquare size={20} className="mr-2" />
            Recent Posts
          </Button>
        </div>

        {/* Feed Slide-out Panel */}
        {showFeed && (
          <>
            {/* Invisible click area to close (only on larger screens) */}
            <div 
              className="fixed top-20 bottom-4 left-0 right-0 z-40 hidden sm:block"
              onClick={closeFeed}
            ></div>

            {/* Slide-out Panel */}
            <div 
              className={`fixed top-16 right-0 bottom-0 w-full sm:top-20 sm:right-4 sm:bottom-4 sm:w-80 md:w-96 lg:w-[28rem] bg-background/85 backdrop-blur-lg shadow-2xl z-50 transform transition-transform duration-300 ease-in-out border border-border sm:rounded-2xl overflow-hidden ring-1 ring-black/5 dark:ring-white/10 ${
                feedAnimating ? 'translate-x-0' : 'translate-x-full'
              }`}
            >
              <div className="flex flex-col h-full">
                {/* Header */}
                <div className="flex items-center justify-between p-3 border-b border-border flex-shrink-0 bg-muted/30">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-sm">
                      <MessageSquare size={16} />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-foreground">Recent Posts</h3>
                      <p className="text-xs text-muted-foreground">Latest posts from {list.name}</p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={closeFeed}
                    className="rounded-full p-1.5 hover:bg-accent"
                  >
                    <X size={16} />
                  </Button>
                </div>

                {/* Feed Content */}
                <div className="flex-1 overflow-y-auto p-3">
                  <ListFeed listId={parseInt(listId!)} listName={list.name} compact={true} />
                </div>
              </div>
            </div>
          </>
        )}

        {/* Brainlifts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {paginatedMembers.map((member) => {
            const totalActivity = (member.tweetCount || 0) + (member.threadCount || 0);
            const hasActivity = totalActivity > 0;
            
            return (
              <div
                key={member.id}
                className="hover:shadow-lg transition-all hover:scale-[1.02] cursor-pointer"
                onClick={() => handleMemberClick(member.id)}
              >
                <Card>
                  <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    {/* Profile Picture */}
                    <div className="flex-shrink-0">
                      <img
                        src={member.profilePicture || '/api/placeholder/48/48'}
                        alt={member.displayName}
                        className="w-12 h-12 rounded-full"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = '/api/placeholder/48/48';
                        }}
                      />
                    </div>

                    {/* Member Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div className="min-w-0">
                          <p className="font-medium truncate">{member.displayName}</p>
                          <p className="text-sm text-muted-foreground truncate">@{member.username}</p>
                        </div>
                        <ExternalLink size={14} className="text-muted-foreground flex-shrink-0 ml-2" />
                      </div>

                      {/* Activity Stats */}
                      <div className="mt-3 space-y-1">
                        {hasActivity ? (
                          <>
                            <div className="flex items-center gap-4 text-xs">
                              <span className="flex items-center gap-1">
                                <Activity size={12} />
                                {totalActivity} total
                              </span>
                              {member.tweetCount! > 0 && (
                                <span>{member.tweetCount} tweets</span>
                              )}
                              {member.threadCount! > 0 && (
                                <span>{member.threadCount} threads</span>
                              )}
                            </div>
                            {member.lastActivity && (
                              <p className="text-xs text-muted-foreground">
                                Last active: {new Date(member.lastActivity).toLocaleDateString()}
                              </p>
                            )}
                          </>
                        ) : (
                          <Badge variant="secondary" className="text-xs">
                            No activity
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  </CardContent>
                </Card>
              </div>
            );
          })}
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6 py-4 border-t">
            <div className="text-sm text-muted-foreground">
              Showing {(currentPage - 1) * BRAINLIFTS_PER_PAGE + 1} to{' '}
              {Math.min(currentPage * BRAINLIFTS_PER_PAGE, list.members.length)} of{' '}
              {list.members.length} brainlifts
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                disabled={currentPage === 1}
              >
                <ChevronLeft size={16} className="mr-1" />
                Previous
              </Button>
              
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <Button
                      key={pageNum}
                      variant={pageNum === currentPage ? 'primary' : 'ghost'}
                      size="sm"
                      onClick={() => setCurrentPage(pageNum)}
                      className="w-8 h-8 p-0"
                    >
                      {pageNum}
                    </Button>
                  );
                })}
              </div>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                disabled={currentPage === totalPages}
              >
                Next
                <ChevronRight size={16} className="ml-1" />
              </Button>
            </div>
          </div>
        )}

        {list.members.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">This list has no brainlifts</p>
          </div>
        )}
      </div>
    </>
  );
};