import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Calendar, MessageSquare, Heart, Repeat2, Share, MoreHorizontal, ChevronDown, ChevronRight, Hash, CheckCircle, XCircle, Clock, ChevronLeft, TrendingUp, BarChart3, Activity } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import { TwitterAccount, Thread, ThreadTweet, Tweet } from '../types';
import { formatDistanceToNow, format } from 'date-fns';
import toast from 'react-hot-toast';
import { cn } from '../utils/cn';
import { getAvatarColor, getAvatarText } from '../utils/avatar';

const THREADS_PER_PAGE = 10;

export const AccountDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [account, setAccount] = useState<TwitterAccount | null>(null);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [individualTweets, setIndividualTweets] = useState<Tweet[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingThreads, setLoadingThreads] = useState(true);
  const [expandedThreads, setExpandedThreads] = useState<Set<string>>(new Set());
  const [threadDetails, setThreadDetails] = useState<Map<string, Thread>>(new Map());
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedTimeRange, setSelectedTimeRange] = useState<'all' | 'week' | 'month'>('all');
  const [contentView, setContentView] = useState<'threads' | 'changes' | 'all'>('all');

  useEffect(() => {
    if (id) {
      loadAccountData(parseInt(id));
    }
  }, [id]);

  const loadAccountData = async (accountId: number) => {
    try {
      setLoading(true);
      setLoadingThreads(true);

      // Load account details
      const accountData = await apiClient.getAccount(accountId);
      setAccount(accountData);

      // Load threads and changes in parallel
      const [accountThreads, allTweets] = await Promise.all([
        apiClient.getThreads(accountId),
        apiClient.getTweets()
      ]);

      // Filter changes for this account that are NOT part of threads
      const accountTweets = allTweets.filter(tweet => 
        tweet.username === accountData.username && !tweet.threadId
      );

      setIndividualTweets(accountTweets.sort((a, b) => 
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      ));

      setThreads(accountThreads.sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      ));
    } catch (error) {
      toast.error('Failed to load account data');
      console.error('Account detail error:', error);
    } finally {
      setLoading(false);
      setLoadingThreads(false);
    }
  };

  const loadThreadDetails = async (threadId: string) => {
    if (threadDetails.has(threadId)) {
      return; // Already loaded
    }

    try {
      const details = await apiClient.getThreadDetails(threadId);
      setThreadDetails(prev => new Map(prev).set(threadId, details));
    } catch (error) {
      toast.error('Failed to load thread details');
      console.error('Thread details error:', error);
    }
  };


  const toggleThread = async (threadId: string) => {
    // Load thread details if not already loaded
    if (!threadDetails.has(threadId)) {
      await loadThreadDetails(threadId);
    }

    setExpandedThreads(prev => {
      const newSet = new Set(prev);
      if (newSet.has(threadId)) {
        newSet.delete(threadId);
      } else {
        newSet.add(threadId);
      }
      return newSet;
    });
  };

  const formatChangeTime = (date: string) => {
    return formatDistanceToNow(new Date(date), { addSuffix: true });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'posted':
        return <CheckCircle size={14} className="text-green-500" />;
      case 'failed':
        return <XCircle size={14} className="text-red-500" />;
      case 'pending':
        return <Clock size={14} className="text-yellow-500" />;
      default:
        return null;
    }
  };

  // Filter threads by time range
  const filteredThreads = threads.filter(thread => {
    if (selectedTimeRange === 'all') return true;
    const threadDate = new Date(thread.created_at);
    const now = new Date();
    const daysDiff = (now.getTime() - threadDate.getTime()) / (1000 * 60 * 60 * 24);
    
    if (selectedTimeRange === 'week') return daysDiff <= 7;
    if (selectedTimeRange === 'month') return daysDiff <= 30;
    return true;
  });

  // Pagination
  const totalPages = Math.ceil(filteredThreads.length / THREADS_PER_PAGE);
  const paginatedThreads = filteredThreads.slice(
    (currentPage - 1) * THREADS_PER_PAGE,
    currentPage * THREADS_PER_PAGE
  );

  // Stats calculations
  const totalThreadChanges = threads.reduce((sum, thread) => sum + thread.tweet_count, 0);
  const totalIndividualChanges = individualTweets.length;
  const totalChanges = totalThreadChanges + totalIndividualChanges;
  const totalPosted = threads.reduce((sum, thread) => sum + thread.posted_count, 0) + 
    individualTweets.filter(t => t.status === 'posted').length;
  const totalPending = threads.reduce((sum, thread) => sum + thread.pending_count, 0) +
    individualTweets.filter(t => t.status === 'pending').length;

  // Calculate engagement stats (mock data for now)
  const engagementRate = 2.4;
  const avgChangesPerThread = threads.length > 0 ? (totalChanges / threads.length).toFixed(1) : '0';
  const postsThisWeek = threads.filter(t => {
    const threadDate = new Date(t.created_at);
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    return threadDate >= weekAgo;
  }).length;

  const renderIndividualChange = (change: Tweet) => (
    <Card key={change.id} className="overflow-hidden hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex gap-3">
          {/* Profile Picture */}
          <div className="flex-shrink-0">
            <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getAvatarColor(account?.username || '')} flex items-center justify-center text-white font-semibold text-sm`}>
              {getAvatarText(account?.username || '', account?.displayName)}
            </div>
          </div>

          {/* Change Content */}
          <div className="flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-1 text-sm">
                <span className="font-semibold">{account?.displayName || account?.username}</span>
                <span className="text-muted-foreground">@{account?.username}</span>
                <span className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">{formatChangeTime(change.postedAt || change.createdAt)}</span>
                {getStatusIcon(change.status)}
              </div>
            </div>

            {/* Change Text */}
            <div className="mt-1 text-sm whitespace-pre-wrap break-words">
              {change.content}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const renderThreadChange = (change: ThreadTweet, isLast: boolean = false) => (
    <div key={change.id} className={cn(
      "relative",
      !isLast && "pb-6"
    )}>
      {/* Connection line */}
      {!isLast && (
        <div className="absolute left-5 top-12 bottom-0 w-0.5 bg-muted" />
      )}
      
      <div className="flex gap-3 relative">
        {/* Profile Picture */}
        <div className="flex-shrink-0 z-10 bg-background">
          <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getAvatarColor(account?.username || '')} flex items-center justify-center text-white font-semibold text-sm`}>
            {getAvatarText(account?.username || '', account?.displayName)}
          </div>
        </div>

        {/* Change Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1 text-sm">
              <span className="font-semibold">{account?.displayName || account?.username}</span>
              <span className="text-muted-foreground">@{account?.username}</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{formatChangeTime(change.posted_at || change.created_at)}</span>
              {getStatusIcon(change.status)}
            </div>
            <Badge variant="outline" className="text-xs">
              {change.position + 1}
            </Badge>
          </div>

          {/* Change Text */}
          <div className="mt-1 text-sm whitespace-pre-wrap break-words">
            {change.content}
          </div>
        </div>
      </div>
    </div>
  );

  // Preload thread details for visible threads
  useEffect(() => {
    const loadVisibleThreadDetails = async () => {
      // Load details for currently visible threads
      const visibleThreads = paginatedThreads.filter(thread => !threadDetails.has(thread.thread_id));
      if (visibleThreads.length > 0) {
        await Promise.all(visibleThreads.map(thread => loadThreadDetails(thread.thread_id)));
      }
    };
    loadVisibleThreadDetails();
  }, [paginatedThreads]);

  const renderThread = (thread: Thread) => {
    const isExpanded = expandedThreads.has(thread.thread_id);
    const details = threadDetails.get(thread.thread_id);
    const hasDetails = details && details.tweets && details.tweets.length > 0;

    // Extract topic from the first change if we have details
    let topic = 'Loading...';
    if (hasDetails && details.tweets[0]) {
      const firstChange = details.tweets[0].content;
      const topicMatch = firstChange.match(/(DOK\d+|SPOV[\s\d.]+):|^([^:]+):/i);
      topic = topicMatch ? (topicMatch[1] || topicMatch[2] || 'Thread').trim() : 'Thread';
    } else if (!threadDetails.has(thread.thread_id)) {
      topic = 'Thread';
    }

    return (
      <Card key={thread.thread_id} className="overflow-hidden hover:shadow-md transition-shadow">
        <button
          onClick={() => toggleThread(thread.thread_id)}
          className="w-full hover:bg-muted/30 transition-colors text-left"
        >
          <CardContent className="p-4">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  {isExpanded ? (
                    <ChevronDown size={20} className="text-muted-foreground" />
                  ) : (
                    <ChevronRight size={20} className="text-muted-foreground" />
                  )}
                  <Hash size={16} className="text-blue-500" />
                  <h3 className="font-semibold line-clamp-1">{topic}</h3>
                  <div className="flex items-center gap-2 ml-auto">
                    {thread.posted_count > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {thread.posted_count} posted
                      </Badge>
                    )}
                    {thread.pending_count > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {thread.pending_count} pending
                      </Badge>
                    )}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {format(new Date(thread.created_at), 'MMM d, yyyy')} • {thread.tweet_count} change{thread.tweet_count !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          </CardContent>
        </button>

        {isExpanded && hasDetails && (
          <div className="border-t border-border p-4 bg-muted/10">
            <div className="space-y-0">
              {details.tweets && details.tweets
                .filter(tweet => tweet.status !== 'failed')
                .map((tweet, index, filteredTweets) => 
                  renderThreadChange(tweet, index === filteredTweets.length - 1)
              )}
            </div>
          </div>
        )}

        {isExpanded && !hasDetails && (
          <div className="border-t border-border p-4">
            <div className="flex justify-center py-4">
              <Skeleton className="h-20 w-full" />
            </div>
          </div>
        )}
      </Card>
    );
  };

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <Skeleton className="h-32 mb-6" />
          <div className="space-y-4">
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        </div>
      </>
    );
  }

  if (!account) {
    return (
      <>
        <TopBar />
        <div className="p-6 text-center">
          <p className="text-muted-foreground mb-4">The account you're looking for doesn't exist.</p>
          <Link to="/accounts">
            <Button variant="secondary">
              <ArrowLeft size={16} className="mr-2" />
              Back to Accounts
            </Button>
          </Link>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Back Button */}
        <Link to="/accounts" className="inline-flex mb-6">
          <Button variant="ghost" size="sm">
            <ArrowLeft size={16} className="mr-2" />
            Back to Accounts
          </Button>
        </Link>

        {/* Account Header */}
        <Card className="mb-6">
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              {/* Large Profile Picture */}
              <div className={`w-20 h-20 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white text-2xl font-semibold`}>
                {getAvatarText(account.username, account.displayName)}
              </div>

              {/* Account Info */}
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">{account.displayName || account.username}</h2>
                    <p className="text-muted-foreground">@{account.username}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">
                      {account.authorized ? 'Active' : 'Inactive'}
                    </Badge>
                    <Badge variant="outline">
                      {account.accountType === 'list_owner' ? 'List Owner' : 'Managed'}
                    </Badge>
                  </div>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-6 mt-4 text-sm">
                  <div>
                    <span className="font-semibold">{threads.length}</span>
                    <span className="text-muted-foreground ml-1">Threads</span>
                  </div>
                  <div>
                    <span className="font-semibold">{totalChanges}</span>
                    <span className="text-muted-foreground ml-1">Total Changes</span>
                  </div>
                  <div>
                    <span className="font-semibold">{totalPosted}</span>
                    <span className="text-muted-foreground ml-1">Posted</span>
                  </div>
                  {totalPending > 0 && (
                    <div>
                      <span className="font-semibold text-yellow-600">{totalPending}</span>
                      <span className="text-muted-foreground ml-1">Pending</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Calendar size={14} />
                    <span>Joined {new Date(account.createdAt).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Threads List - 2 columns on large screens */}
          <div className="lg:col-span-2">
            {/* Filters and Header */}
            <div className="space-y-4 mb-4">
              {/* Content Type Toggle */}
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Content</h3>
                <div className="flex items-center gap-1 bg-muted p-1 rounded-lg">
                  <Button
                    variant={contentView === 'all' ? 'primary' : 'ghost'}
                    size="sm"
                    onClick={() => {
                      setContentView('all');
                      setCurrentPage(1);
                    }}
                  >
                    All
                  </Button>
                  {threads.length > 0 && (
                    <Button
                      variant={contentView === 'threads' ? 'primary' : 'ghost'}
                      size="sm"
                      onClick={() => {
                        setContentView('threads');
                        setCurrentPage(1);
                      }}
                    >
                      Threads ({threads.length})
                    </Button>
                  )}
                  {individualTweets.length > 0 && (
                    <Button
                      variant={contentView === 'changes' ? 'primary' : 'ghost'}
                      size="sm"
                      onClick={() => {
                        setContentView('changes');
                        setCurrentPage(1);
                      }}
                    >
                      Changes ({individualTweets.length})
                    </Button>
                  )}
                </div>
              </div>

              {/* Time Filters */}
              <div className="flex items-center gap-2">
                <Button
                  variant={selectedTimeRange === 'all' ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => {
                    setSelectedTimeRange('all');
                    setCurrentPage(1);
                  }}
                >
                  All Time
                </Button>
                <Button
                  variant={selectedTimeRange === 'week' ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => {
                    setSelectedTimeRange('week');
                    setCurrentPage(1);
                  }}
                >
                  This Week
                </Button>
                <Button
                  variant={selectedTimeRange === 'month' ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => {
                    setSelectedTimeRange('month');
                    setCurrentPage(1);
                  }}
                >
                  This Month
                </Button>
              </div>
            </div>
            
            {/* Content Display */}
            {loadingThreads ? (
              <div className="space-y-4">
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
                <Skeleton className="h-24" />
              </div>
            ) : (
              <>
                {/* Show Threads */}
                {(contentView === 'threads' || contentView === 'all') && threads.length > 0 && (
                  <div className="space-y-3">
                    {contentView === 'all' && individualTweets.length > 0 && (
                      <h4 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">Threads</h4>
                    )}
                    {paginatedThreads.map(renderThread)}
                  </div>
                )}

                {/* Show Individual Changes */}
                {(contentView === 'changes' || contentView === 'all') && individualTweets.length > 0 && (
                  <div className="space-y-3 mt-6">
                    {contentView === 'all' && threads.length > 0 && (
                      <h4 className="font-medium text-sm text-muted-foreground uppercase tracking-wide">Individual Changes</h4>
                    )}
                    {individualTweets
                      .filter(tweet => tweet.status !== 'failed')
                      .slice((currentPage - 1) * THREADS_PER_PAGE, currentPage * THREADS_PER_PAGE)
                      .map(renderIndividualChange)}
                  </div>
                )}

                {/* No Content */}
                {((contentView === 'threads' && filteredThreads.length === 0) ||
                  (contentView === 'changes' && individualTweets.length === 0) ||
                  (contentView === 'all' && filteredThreads.length === 0 && individualTweets.length === 0)) && (
                  <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                      No {contentView === 'all' ? 'content' : contentView} found {selectedTimeRange !== 'all' && 'in this time range'}
                    </CardContent>
                  </Card>
                )}

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-6">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                    >
                      <ChevronLeft size={16} />
                    </Button>
                    <span className="text-sm text-muted-foreground">
                      Page {currentPage} of {totalPages}
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                    >
                      <ChevronRight size={16} />
                    </Button>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Stats Sidebar */}
          <div className="space-y-4">
            {/* Performance Stats */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <BarChart3 size={18} className="text-blue-500" />
                  Performance Stats
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Engagement Rate</span>
                    <span className="text-sm font-semibold">{engagementRate}%</span>
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <TrendingUp size={14} className="text-green-500" />
                    <span className="text-xs text-green-600">+0.3% from last week</span>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Avg Changes/Thread</span>
                    <span className="text-sm font-semibold">{avgChangesPerThread}</span>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Posts This Week</span>
                    <span className="text-sm font-semibold">{postsThisWeek}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Activity Timeline */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity size={18} className="text-purple-500" />
                  Recent Activity
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {threads.slice(0, 5).map((thread, index) => (
                    <div key={thread.thread_id} className="flex items-start gap-2">
                      <div className={cn(
                        "w-2 h-2 rounded-full mt-1.5",
                        thread.posted_count > 0 ? "bg-green-500" : "bg-yellow-500"
                      )} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm line-clamp-1">
                          {thread.tweet_count} change{thread.tweet_count !== 1 ? 's' : ''} posted
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatChangeTime(thread.created_at)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Quick Stats */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Thread Distribution</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Single changes</span>
                    <span className="font-semibold">
                      {threads.filter(t => t.tweet_count === 1).length}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Short threads (2-5)</span>
                    <span className="font-semibold">
                      {threads.filter(t => t.tweet_count >= 2 && t.tweet_count <= 5).length}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Long threads (6+)</span>
                    <span className="font-semibold">
                      {threads.filter(t => t.tweet_count > 5).length}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </>
  );
};