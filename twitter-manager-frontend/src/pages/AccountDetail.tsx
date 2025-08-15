import React, { useEffect, useState, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Calendar, ChevronDown, ChevronRight, Hash, CheckCircle, XCircle, Clock, ChevronLeft, TrendingUp, BarChart3, Activity, Shield, Users, Zap, Target, Flame, Timer, TrendingDown, ExternalLink, FileText } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import { TwitterAccount, Thread, ThreadTweet, Tweet } from '../types';
import { formatDistanceToNow, format, subDays, startOfDay } from 'date-fns';
import toast from 'react-hot-toast';
import { cn } from '../utils/cn';
import { getAvatarColor, getAvatarText } from '../utils/avatar';
import { CompactFollowerList } from '../components/followers/CompactFollowerList';
import { MiniChart } from '../components/charts/MiniChart';
import { ActivityHeatmap } from '../components/charts/ActivityHeatmap';

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
  const [savedFollowerCount, setSavedFollowerCount] = useState(0);

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

      // Load threads and tweets
      const [accountThreads, allTweets] = await Promise.all([
        apiClient.getThreads(accountId),
        apiClient.getTweets()
      ]);
      
      // Try to load saved followers count separately to prevent blocking if it fails
      try {
        const savedFollowersData = await apiClient.getSavedFollowers(accountId, 1, 1);
        setSavedFollowerCount(savedFollowersData.pagination?.total || 0);
      } catch (error) {
        console.error('Failed to load saved followers count:', error);
        setSavedFollowerCount(0);
      }

      // Filter tweets for this account that are NOT part of threads
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

  const formatChangeTime = (date: string | null | undefined) => {
    if (!date) {
      return 'recently';
    }
    try {
      const parsedDate = new Date(date);
      if (isNaN(parsedDate.getTime())) {
        return 'recently';
      }
      return formatDistanceToNow(parsedDate, { addSuffix: true });
    } catch (error) {
      console.error('Error formatting date:', date, error);
      return 'recently';
    }
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

  // Stats calculations - use account stats if available, otherwise calculate from local data
  const totalIndividualTweets = account?.stats?.standalone_tweets || individualTweets.length;
  const totalThreads = account?.stats?.total_threads || threads.length;
  const totalPosts = totalIndividualTweets + totalThreads; // Combined posts count
  
  // Count posted items: individual tweets with status='posted' + threads where all tweets are posted
  const postedTweets = individualTweets.filter(t => t.status === 'posted').length;
  const postedThreads = threads.filter(t => t.posted_count > 0 && t.posted_count === t.tweet_count).length;
  const totalPosted = postedTweets + postedThreads;

  // Calculate engagement stats (mock data for now)
  const engagementRate = 2.4;
  const avgPostsPerWeek = totalPosts > 0 ? (totalPosts / 4).toFixed(1) : '0'; // Rough estimate for past 4 weeks
  const postsThisWeek = threads.filter(t => {
    const threadDate = new Date(t.created_at);
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    return threadDate >= weekAgo;
  }).length;

  // Advanced metrics calculations
  const last28DaysData = useMemo(() => {
    const days = Array.from({ length: 28 }, (_, i) => {
      const date = subDays(new Date(), 27 - i);
      const dateStr = format(date, 'yyyy-MM-dd');
      
      const dayThreads = threads.filter(t => 
        format(new Date(t.created_at), 'yyyy-MM-dd') === dateStr
      );
      
      const dayTweets = individualTweets.filter(t => 
        format(new Date(t.createdAt), 'yyyy-MM-dd') === dateStr
      );
      
      return {
        date: dateStr,
        count: dayThreads.length + dayTweets.length,
        threads: dayThreads.length,
        tweets: dayTweets.length
      };
    });
    
    return days;
  }, [threads, individualTweets]);

  // Activity heatmap data - full year
  const activityData = useMemo(() => {
    const data: { date: string; count: number }[] = [];
    const today = new Date();
    
    // Generate data for the last 365 days
    for (let i = 0; i < 365; i++) {
      const date = subDays(today, i);
      const dateStr = format(date, 'yyyy-MM-dd');
      
      const dayCount = threads.filter(t => 
        format(new Date(t.created_at), 'yyyy-MM-dd') === dateStr
      ).length + individualTweets.filter(t => 
        format(new Date(t.createdAt), 'yyyy-MM-dd') === dateStr
      ).length;
      
      data.unshift({ date: dateStr, count: dayCount });
    }
    
    return data;
  }, [threads, individualTweets]);

  // Calculate posting consistency
  const postingConsistency = useMemo(() => {
    const daysWithPosts = last28DaysData.filter(d => d.count > 0).length;
    return Math.round((daysWithPosts / 28) * 100);
  }, [last28DaysData]);

  // Calculate best posting hour (mock for now)
  const bestPostingHour = useMemo(() => {
    const hours = threads.map(t => new Date(t.created_at).getHours());
    if (hours.length === 0) return 14; // Default to 2 PM
    const hourCounts = hours.reduce((acc, hour) => {
      acc[hour] = (acc[hour] || 0) + 1;
      return acc;
    }, {} as Record<number, number>);
    
    return parseInt(Object.entries(hourCounts)
      .sort(([, a], [, b]) => b - a)[0]?.[0] || '14');
  }, [threads]);

  // Calculate streak
  const currentStreak = useMemo(() => {
    let streak = 0;
    const today = startOfDay(new Date());
    
    for (let i = 0; i < 365; i++) {
      const date = subDays(today, i);
      const dateStr = format(date, 'yyyy-MM-dd');
      
      const hasActivity = threads.some(t => 
        format(new Date(t.created_at), 'yyyy-MM-dd') === dateStr
      ) || individualTweets.some(t => 
        format(new Date(t.createdAt), 'yyyy-MM-dd') === dateStr
      );
      
      if (hasActivity) {
        streak++;
      } else if (i > 0) {
        break;
      }
    }
    
    return streak;
  }, [threads, individualTweets]);


  const renderIndividualTweet = (tweet: Tweet) => (
    <Card key={tweet.id} className="overflow-hidden hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex gap-3">
          {/* Profile Picture */}
          <div className="flex-shrink-0">
            {account?.profilePicture ? (
              <img 
                src={account.profilePicture}
                alt={account?.displayName || account?.username}
                className="w-10 h-10 rounded-full object-cover"
              />
            ) : (
              <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getAvatarColor(account?.username || '')} flex items-center justify-center text-white font-semibold text-sm`}>
                {getAvatarText(account?.username || '', account?.displayName)}
              </div>
            )}
          </div>

          {/* Change Content */}
          <div className="flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-1 text-sm">
                <span className="font-semibold">{account?.displayName || account?.username}</span>
                <a 
                  href={`https://x.com/${account?.username}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-muted-foreground hover:text-primary transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  @{account?.username}
                </a>
                <span className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">{formatChangeTime(tweet.postedAt || tweet.createdAt)}</span>
                {getStatusIcon(tweet.status)}
              </div>
            </div>

            {/* Change Text */}
            <div className="mt-1 text-sm whitespace-pre-wrap break-words">
              {tweet.content}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  const renderThreadTweet = (tweet: ThreadTweet, isLast: boolean = false) => (
    <div className={cn(
      "relative",
      !isLast && "pb-6"
    )}>
      {/* Connection line */}
      {!isLast && (
        <div className="absolute left-5 top-12 bottom-0 w-0.5 bg-muted" />
      )}
      
      <div className="flex gap-3 relative">
        {/* Profile Picture */}
        <div className="flex-shrink-0 z-10">
          {account?.profilePicture ? (
            <img 
              src={account.profilePicture}
              alt={account?.displayName || account?.username}
              className="w-10 h-10 rounded-full object-cover"
            />
          ) : (
            <div className={`w-10 h-10 rounded-full bg-gradient-to-br ${getAvatarColor(account?.username || '')} flex items-center justify-center text-white font-semibold text-sm`}>
              {getAvatarText(account?.username || '', account?.displayName)}
            </div>
          )}
        </div>

        {/* Change Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-1 text-sm">
              <span className="font-semibold">{account?.displayName || account?.username}</span>
              <span className="text-muted-foreground">@{account?.username}</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{formatChangeTime(tweet.posted_at || tweet.created_at)}</span>
              {getStatusIcon(tweet.status)}
            </div>
            <Badge variant="outline" className="text-xs">
              {tweet.position + 1}
            </Badge>
          </div>

          {/* Change Text */}
          <div className="mt-1 text-sm whitespace-pre-wrap break-words">
            {tweet.content}
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

    // Extract topic from the first tweet if we have details
    let topic = 'Loading...';
    if (hasDetails && details.tweets && details.tweets[0]) {
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
                    {thread.posted_count && thread.posted_count > 0 && (
                      <Badge variant="secondary" className="text-xs">
                        {thread.posted_count || 0} posted
                      </Badge>
                    )}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {format(new Date(thread.created_at), 'MMM d, yyyy')} • {thread.tweet_count} post{thread.tweet_count !== 1 ? 's' : ''}
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
                .map((tweet, index, filteredTweets) => (
                  <React.Fragment key={tweet.id || `tweet-${index}`}>
                    {renderThreadTweet(tweet, index === filteredTweets.length - 1)}
                  </React.Fragment>
                )
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

        {/* Account Header - Twitter Analytics Style */}
        <Card className="mb-6 overflow-hidden border-0 shadow-lg">
          <CardContent className="p-6">
            <div className="flex items-end gap-4 mb-4">
              {/* Large Profile Picture */}
              <div className="relative">
                {account.profilePicture ? (
                  <img 
                    src={account.profilePicture}
                    alt={account.displayName || account.username}
                    className="w-24 h-24 rounded-full object-cover shadow-xl"
                  />
                ) : (
                  <div className={`w-24 h-24 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white text-3xl font-bold shadow-xl`}>
                    {getAvatarText(account.username, account.displayName)}
                  </div>
                )}
                {account.verified && (
                  <div className="absolute -bottom-1 -right-1 bg-background rounded-full p-1 shadow-lg">
                    <Shield size={20} className="text-blue-500 fill-blue-500" />
                  </div>
                )}
              </div>

              {/* Account Info */}
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-2xl font-bold flex items-center gap-2">
                      {account.displayName || account.username}
                      {account.verified && <Shield size={20} className="text-blue-500 fill-blue-500" />}
                    </h2>
                    <div className="flex flex-col">
                      <a 
                        href={`https://x.com/${account.username}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground text-lg hover:text-primary transition-colors"
                      >
                        @{account.username}
                      </a>
                      {account.workflowyUrl && (
                        <a
                          href={account.workflowyUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 mt-2 text-sm text-primary hover:text-primary/80 transition-colors"
                        >
                          <FileText size={14} />
                          <span>View Brainlift</span>
                          <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Bio if available */}
            {account.description && (
              <p className="text-muted-foreground mb-4 max-w-3xl">{account.description}</p>
            )}

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mt-6">
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="flex items-center">
                  <Users size={16} className="text-blue-500" />
                </div>
                <div className="text-2xl font-bold mt-1">{savedFollowerCount.toLocaleString()}</div>
                <div className="text-xs text-muted-foreground">Saved Followers</div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="text-2xl font-bold">{totalPosts}</div>
                <div className="text-xs text-muted-foreground">Total Posts</div>
              </div>
              
              <div className="p-3 rounded-lg bg-muted/50">
                <div className="flex items-center gap-1 text-sm font-medium">
                  <Calendar size={14} />
                  {format(new Date(account.createdAt), 'MMM yyyy')}
                </div>
                <div className="text-xs text-muted-foreground">Joined</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* 28-Day Summary - X Analytics Style */}
        <Card className="mb-6 border-0 shadow-lg">
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp size={20} className="text-blue-500" />
                28-Day Summary
              </CardTitle>
              <Badge variant="outline" className="text-xs">
                {format(subDays(new Date(), 27), 'MMM d')} - {format(new Date(), 'MMM d')}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {/* Posting Consistency */}
              <div className="p-4 rounded-lg bg-muted/30 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <Target size={16} className="text-purple-500" />
                  <span className="text-2xl font-bold">{postingConsistency}%</span>
                </div>
                <p className="text-xs text-muted-foreground">Consistency Score</p>
                <div className="mt-2 h-2 bg-muted rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-purple-500 to-purple-600 rounded-full transition-all"
                    style={{ width: `${postingConsistency}%` }}
                  />
                </div>
              </div>

              {/* Current Streak */}
              <div className="p-4 rounded-lg bg-muted/30 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <Flame size={16} className="text-orange-500" />
                  <span className="text-2xl font-bold">{currentStreak}</span>
                </div>
                <p className="text-xs text-muted-foreground">Day Streak</p>
                <div className="mt-2">
                  <MiniChart 
                    data={last28DaysData.slice(-7).map(d => d.count)}
                    height={20}
                    width={80}
                    color="text-orange-500"
                    type="bar"
                  />
                </div>
              </div>

              {/* Best Posting Time */}
              <div className="p-4 rounded-lg bg-muted/30 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <Timer size={16} className="text-green-500" />
                  <span className="text-2xl font-bold">{bestPostingHour}:00</span>
                </div>
                <p className="text-xs text-muted-foreground">Best Hour</p>
                <p className="text-xs text-green-600 mt-2">Peak activity time</p>
              </div>

              {/* Content Velocity */}
              <div className="p-4 rounded-lg bg-muted/30 border border-border">
                <div className="flex items-center justify-between mb-2">
                  <Zap size={16} className="text-yellow-500" />
                  <div className="flex items-center gap-1">
                    <span className="text-2xl font-bold">{postsThisWeek}</span>
                    {postsThisWeek > 5 ? (
                      <TrendingUp size={14} className="text-green-500" />
                    ) : (
                      <TrendingDown size={14} className="text-red-500" />
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">This Week</p>
                <div className="mt-2">
                  <MiniChart 
                    data={last28DaysData.map(d => d.count)}
                    height={20}
                    width={80}
                    color="text-yellow-500"
                    showDots={false}
                  />
                </div>
              </div>
            </div>

            {/* Activity Heatmap */}
            <div className="mt-6">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium flex items-center gap-2">
                  <Activity size={14} />
                  Contribution Activity
                </h4>
                <span className="text-xs text-muted-foreground">
                  {activityData.reduce((sum, d) => sum + d.count, 0)} contributions in the last year
                </span>
              </div>
              <div className="p-4 bg-muted/20 rounded-lg overflow-x-auto">
                <ActivityHeatmap data={activityData} weeks={52} />
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
                    variant="primary"
                    size="sm"
                  >
                    Posts ({threads.length + individualTweets.length})
                  </Button>
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
                {/* Show All Posts (Threads and Tweets combined) */}
                {(threads.length > 0 || individualTweets.length > 0) ? (
                  <div className="space-y-3">
                    {/* Show threads first */}
                    {paginatedThreads.map(renderThread)}
                    {/* Then show individual tweets if on first page and have room */}
                    {currentPage === 1 && paginatedThreads.length < THREADS_PER_PAGE && 
                      individualTweets
                        .filter(tweet => tweet.status !== 'failed')
                        .slice(0, THREADS_PER_PAGE - paginatedThreads.length)
                        .map(renderIndividualTweet)
                    }
                  </div>
                ) : (
                  <Card>
                    <CardContent className="p-8 text-center text-muted-foreground">
                      No posts found {selectedTimeRange !== 'all' && 'in this time range'}
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
            {/* Performance Stats - Analytics Style */}
            <Card className="overflow-hidden">
              <CardHeader className="pb-3 bg-muted/50">
                <CardTitle className="text-base flex items-center gap-2">
                  <BarChart3 size={18} className="text-blue-500" />
                  Performance Metrics
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 pt-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Engagement Rate</span>
                    <div className="flex items-center gap-2">
                      <span className="text-lg font-bold">{engagementRate}%</span>
                      <div className="flex items-center gap-0.5 text-green-600">
                        <TrendingUp size={14} />
                        <span className="text-xs">+0.3%</span>
                      </div>
                    </div>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full" style={{width: `${engagementRate * 10}%`}} />
                  </div>
                </div>
                
                <div className="pt-2 space-y-3 border-t">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Avg Posts/Week</span>
                    <span className="text-sm font-bold bg-muted px-2 py-0.5 rounded">{avgPostsPerWeek}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Posts This Week</span>
                    <span className="text-sm font-bold bg-muted px-2 py-0.5 rounded">{postsThisWeek}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Success Rate</span>
                    <span className="text-sm font-bold bg-muted px-2 py-0.5 rounded">
                      {totalPosts > 0 ? Math.round((totalPosted / totalPosts) * 100) : 0}%
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Followers */}
            <CompactFollowerList accountId={account.id} />

            {/* Activity Timeline */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity size={18} className="text-purple-500" />
                  Recent Updates
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {threads.slice(0, 5).map((thread) => (
                    <div key={thread.thread_id} className="flex items-start gap-2">
                      <div className={cn(
                        "w-2 h-2 rounded-full mt-1.5",
                        thread.posted_count > 0 ? "bg-green-500" : "bg-yellow-500"
                      )} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm line-clamp-1">
                          {thread.tweet_count} post{thread.tweet_count !== 1 ? 's' : ''}
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

          </div>
        </div>
      </div>
    </>
  );
};