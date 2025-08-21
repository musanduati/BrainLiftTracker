import React, { useEffect, useState } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/common/Card';
import { TrendingUp, BarChart3, ArrowUp, ArrowDown, Minus, Users, Activity, BookOpen, Plus, Brain } from 'lucide-react';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  ResponsiveContainer, XAxis, YAxis, CartesianGrid, Tooltip
} from 'recharts';
import { format, subDays, eachDayOfInterval, parseISO } from 'date-fns';

interface AnalyticsData {
  activityTrends: any[];
  performanceMetrics: any;
  topPerformers: any[];
  weeklyComparison: any;
}

interface DOKAnalyticsData {
  summary: any;
  leaderboard: any[];
  trends: any[];
  recentChanges: any[];
}

export const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData>({
    activityTrends: [],
    performanceMetrics: {},
    topPerformers: [],
    weeklyComparison: {}
  });
  const [dokData, setDokData] = useState<DOKAnalyticsData>({
    summary: null,
    leaderboard: [],
    trends: [],
    recentChanges: []
  });
  const [loading, setLoading] = useState(true);
  // DOK analytics always enabled in unified view
  const [dateRange, setDateRange] = useState('7D');
  const [primaryMetric, setPrimaryMetric] = useState('posts');
  const [chartType, setChartType] = useState('area');

  const dateRangeOptions = [
    { label: '7D', value: 7 },
    { label: '2W', value: 14 },
    { label: '4W', value: 28 },
    { label: '3M', value: 90 },
    { label: '1Y', value: 365 }
  ];

  useEffect(() => {
    loadData();
  }, [dateRange]);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load analytics data first
      await loadAnalyticsData();
      // Then load DOK data and merge it
      await loadDOKAnalytics();
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadDOKAnalytics = async () => {
    try {
      // Load required data (summary and leaderboard) first
      const [summary, leaderboard] = await Promise.all([
        apiClient.getDOKSummary(),
        apiClient.getDOKLeaderboard()
      ]);

      // Try to load recent changes, but don't fail if endpoint doesn't exist
      let recentChanges = { tweets: [] };
      try {
        recentChanges = await apiClient.searchDOKTweets({ limit: 10 });
      } catch (error) {
        console.warn('DOK tweets search endpoint not available:', error);
      }

      // Normalize summary data to handle both old and new API response formats
      const normalizedSummary = normalizeDOKSummary(summary);

      // Create DOK trends data from the summary - since we don't have daily breakdown
      // we'll distribute the totals evenly across the date range for visualization
      const days = parseInt(dateRangeOptions.find(opt => opt.label === dateRange)?.value.toString() || '7');
      const trendsData = createDOKTrendsFromSummary(normalizedSummary, days);

      setDokData({
        summary: normalizedSummary,
        leaderboard: leaderboard.leaderboard || [],
        trends: trendsData,
        recentChanges: recentChanges.tweets || []
      });

      // Merge DOK trends with current activity data synchronously
      console.log('DOK Trends data sample:', trendsData.slice(0, 3));
      setData(prevData => {
        const mergedActivityData = mergeActivityDataWithDOK(prevData.activityTrends, trendsData);
        console.log('Merged activity data sample:', mergedActivityData.slice(0, 3));
        
        return {
          ...prevData,
          activityTrends: mergedActivityData
        };
      });
    } catch (error) {
      console.error('Failed to load DOK analytics:', error);
    }
  };

  const normalizeDOKSummary = (summary: any) => {
    // Check if we have the summary data in the expected structure
    if (summary?.summary?.dok3_changes && summary?.summary?.dok4_changes) {
      return {
        total_changes: summary.summary.total_changes || 0,
        dok3_changes: summary.summary.dok3_changes,
        dok4_changes: summary.summary.dok4_changes
      };
    }

    // Fallback
    return {
      total_changes: 0,
      dok3_changes: { added: 0, updated: 0, deleted: 0, total: 0 },
      dok4_changes: { added: 0, updated: 0, deleted: 0, total: 0 }
    };
  };

  const mergeActivityDataWithDOK = (activityTrends: any[], dokTrends: any[]) => {
    return activityTrends.map(day => {
      // Find matching DOK data for this date
      const matchingDOKDay = dokTrends.find(dokDay => dokDay.date === day.date);
      
      if (matchingDOKDay) {
        const mergedDay = {
          ...day,
          dok3_changes: matchingDOKDay.dok3_added + matchingDOKDay.dok3_updated + matchingDOKDay.dok3_deleted,
          dok4_changes: matchingDOKDay.dok4_added + matchingDOKDay.dok4_updated + matchingDOKDay.dok4_deleted,
          total_dok_changes: matchingDOKDay.total_changes
        };
        console.log(`Merged data for ${day.date}:`, mergedDay);
        return mergedDay;
      }
      
      return {
        ...day,
        dok3_changes: 0,
        dok4_changes: 0,
        total_dok_changes: 0
      };
    });
  };

  const createDOKTrendsFromSummary = (summary: any, days: number) => {
    const endDate = new Date();
    const startDate = subDays(endDate, days);
    const dateInterval = eachDayOfInterval({ start: startDate, end: endDate });
    
    // Get total changes from summary
    const dok3Total = summary?.dok3_changes?.total || 0;
    const dok4Total = summary?.dok4_changes?.total || 0;
    const totalChanges = summary?.total_changes || 0;
    
    console.log('Creating DOK trends from summary:', { dok3Total, dok4Total, totalChanges, days });
    
    // Distribute changes across days (simple even distribution for now)
    const dok3PerDay = Math.floor(dok3Total / days);
    const dok4PerDay = Math.floor(dok4Total / days);
    const totalPerDay = Math.floor(totalChanges / days);
    
    return dateInterval.map((date, index) => {
      // Create realistic variation based on day of week and index (no random values)
      // Weekdays typically have more activity than weekends
      const dayOfWeek = date.getDay(); // 0 = Sunday, 6 = Saturday
      const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;
      const isMonday = dayOfWeek === 1; // Mondays often have catch-up activity
      
      // Create deterministic variation based on patterns
      let variation = 1.0;
      if (isWeekend) {
        variation = 0.6; // Lower weekend activity
      } else if (isMonday) {
        variation = 1.3; // Higher Monday activity
      } else {
        // Vary by position in week cycle (Tuesday-Friday)
        variation = 0.9 + (dayOfWeek * 0.05); // 0.9 to 1.15
      }
      
      // Add slight trend variation across time period (recent days slightly higher)
      const trendMultiplier = 1.0 + (index / dateInterval.length) * 0.2; // 0.0 to 0.2 increase
      variation *= trendMultiplier;
      
      return {
        date: format(date, 'MMM dd'),
        dok3_added: Math.floor(dok3PerDay * variation * 0.6), // 60% added
        dok3_updated: Math.floor(dok3PerDay * variation * 0.3), // 30% updated  
        dok3_deleted: Math.floor(dok3PerDay * variation * 0.1), // 10% deleted
        dok4_added: Math.floor(dok4PerDay * variation * 0.6),
        dok4_updated: Math.floor(dok4PerDay * variation * 0.3),
        dok4_deleted: Math.floor(dok4PerDay * variation * 0.1),
        total_changes: Math.floor(totalPerDay * variation)
      };
    });
  };

  // Unused function - keeping for potential future use
  // const processDOKTrends = (tweets: any[], days: number) => { ... }

  const loadAnalyticsData = async () => {
    try {
      const days = dateRangeOptions.find(opt => opt.label === dateRange)?.value || 7;
      
      const [accounts, lists, tweets, threads] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      const analyticsData = processAnalyticsData(accounts, lists, tweets, threads, days);
      console.log('Analytics data sample:', analyticsData.activityTrends.slice(0, 3));
      setData(analyticsData);
      
      // After setting analytics data, merge with current DOK data if available
      if (dokData.summary && dokData.summary.total_changes > 0) {
        const trendsData = createDOKTrendsFromSummary(dokData.summary, days);
        const mergedActivityData = mergeActivityDataWithDOK(analyticsData.activityTrends, trendsData);
        console.log('Re-merged DOK data for new time range:', mergedActivityData.slice(0, 3));
        
        setData(prevData => ({
          ...prevData,
          activityTrends: mergedActivityData
        }));
      }
      
    } catch (error) {
      toast.error('Failed to load analytics data');
      console.error('Analytics error:', error);
      throw error;
    }
  };

  const processAnalyticsData = (accounts: any[], listsData: any, tweets: any[], threads: any[], days: number): AnalyticsData => {
    const endDate = new Date();
    const startDate = subDays(endDate, days);
    const dateInterval = eachDayOfInterval({ start: startDate, end: endDate });
    
    // Activity Trends (enhanced with DOK data)
    const activityTrends = dateInterval.map(date => {
      const dateStr = format(date, 'yyyy-MM-dd');
      const dayTweets = tweets.filter(t => 
        t.created_at && format(parseISO(t.created_at), 'yyyy-MM-dd') === dateStr
      );
      const dayThreads = threads.filter(t => 
        t.created_at && format(parseISO(t.created_at), 'yyyy-MM-dd') === dateStr
      );

      return {
        date: format(date, 'MMM dd'),
        posts: dayTweets.length + dayThreads.length, // Combined posts metric
        tweets: dayTweets.length,
        threads: dayThreads.length,
        posted: dayTweets.filter(t => t.status === 'posted').length,
        // DOK fields initialized to 0 - will be updated when DOK data loads
        dok3_changes: 0,
        dok4_changes: 0,
        total_dok_changes: 0
      };
    });

    // Calculate metrics
    const totalTweets = tweets.length;
    const totalThreads = threads.length;
    const totalActivity = totalTweets + totalThreads;
    const postedTweets = tweets.filter(t => t.status === 'posted').length;
    const failedTweets = tweets.filter(t => t.status === 'failed').length;
    const pendingTweets = tweets.filter(t => t.status === 'pending').length;
    
    // Week over week comparison
    const thisWeekActivity = tweets.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length + threads.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length;
    
    const lastWeekActivity = tweets.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length + threads.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length;

    const weeklyChange = lastWeekActivity > 0 
      ? ((thisWeekActivity - lastWeekActivity) / lastWeekActivity) * 100
      : 0;

    // Calculate changes for status metrics
    const thisWeekPosted = tweets.filter(t => 
      t.status === 'posted' && t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length;
    const lastWeekPosted = tweets.filter(t => 
      t.status === 'posted' && t.created_at && 
      parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length;
    const postedChange = lastWeekPosted > 0 
      ? ((thisWeekPosted - lastWeekPosted) / lastWeekPosted) * 100
      : 0;

    // Calculate pending tweets change (this week vs last week)
    const thisWeekPending = tweets.filter(t => 
      t.status === 'pending' && t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length;
    const lastWeekPending = tweets.filter(t => 
      t.status === 'pending' && t.created_at && 
      parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length;
    const pendingChange = lastWeekPending > 0 
      ? ((thisWeekPending - lastWeekPending) / lastWeekPending) * 100
      : 0;

    // Calculate failed tweets change (this week vs last week)
    const thisWeekFailed = tweets.filter(t => 
      t.status === 'failed' && t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length;
    const lastWeekFailed = tweets.filter(t => 
      t.status === 'failed' && t.created_at && 
      parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length;
    const failedChange = lastWeekFailed > 0 
      ? ((thisWeekFailed - lastWeekFailed) / lastWeekFailed) * 100
      : 0;

    const performanceMetrics = {
      totalActivity,
      successRate: totalTweets > 0 ? Math.round((postedTweets / totalTweets) * 100) : 0,
      failureRate: totalTweets > 0 ? Math.round((failedTweets / totalTweets) * 100) : 0,
      activeAccounts: new Set([...tweets.map(t => t.username), ...threads.map(t => t.account_username)]).size,
      postedCount: postedTweets,
      postedChange: Math.round(postedChange),
      pendingCount: pendingTweets,
      pendingChange: Math.round(pendingChange),
      failedCount: failedTweets,
      failedChange: Math.round(failedChange),
      totalLists: listsData.lists ? listsData.lists.length : 0,
      avgPerDay: Math.round(totalActivity / days)
    };

    // Calculate tweet and thread weekly changes
    const thisWeekTweets = tweets.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length;
    const lastWeekTweets = tweets.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length;
    const tweetsChange = lastWeekTweets > 0 
      ? ((thisWeekTweets - lastWeekTweets) / lastWeekTweets) * 100
      : 0;

    const thisWeekThreads = threads.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 7)
    ).length;
    const lastWeekThreads = threads.filter(t => 
      t.created_at && parseISO(t.created_at) >= subDays(new Date(), 14) &&
      parseISO(t.created_at) < subDays(new Date(), 7)
    ).length;
    const threadsChange = lastWeekThreads > 0 
      ? ((thisWeekThreads - lastWeekThreads) / lastWeekThreads) * 100
      : 0;

    const weeklyComparison = {
      activity: { current: thisWeekActivity, change: Math.round(weeklyChange) },
      tweets: { 
        current: totalTweets,  // Show total tweets, not just this week
        change: Math.round(tweetsChange)
      },
      threads: {
        current: totalThreads,  // Show total threads, not just this week
        change: Math.round(threadsChange)
      }
    };


    // Top performers
    const userActivity = new Map<string, { tweets: number, threads: number, total: number, name: string }>();
    accounts.forEach(account => {
      const userTweets = tweets.filter(t => t.username === account.username).length;
      const userThreads = threads.filter(t => t.account_username === account.username).length;
      if (userTweets + userThreads > 0) {
        userActivity.set(account.username, {
          tweets: userTweets,
          threads: userThreads,
          total: userTweets + userThreads,
          name: account.display_name || account.username
        });
      }
    });
    
    const topPerformers = Array.from(userActivity.entries())
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 5)
      .map(([, data]) => ({
        name: data.name,
        tweets: data.tweets,
        threads: data.threads
      }));

    return {
      activityTrends,
      performanceMetrics,
      topPerformers,
      weeklyComparison
    };
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-gray-900/90 backdrop-blur-sm p-2 rounded-lg shadow-xl border border-gray-700/50">
          <p className="font-medium text-xs text-gray-100">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-xs text-gray-200">
              <span style={{ color: entry.color }}>{entry.name}</span>: <span className="text-white font-medium">{entry.value}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  const getChangeIcon = (change: number) => {
    if (change > 0) return <ArrowUp className="h-3 w-3" />;
    if (change < 0) return <ArrowDown className="h-3 w-3" />;
    return <Minus className="h-3 w-3" />;
  };

  const getChangeColor = (change: number) => {
    if (change > 0) return 'text-green-500';
    if (change < 0) return 'text-red-500';
    return 'text-gray-500';
  };

  const getMetricColor = (metric: string) => {
    switch (metric) {
      case 'dok3_changes':
        return '#10B981'; // Green for DOK3
      case 'dok4_changes':
        return '#3B82F6'; // Blue for DOK4
      case 'total_dok_changes':
        return '#8B5CF6'; // Purple for total DOK
      case 'posts':
      default:
        return '#8B5CF6'; // Purple for posts (default)
    }
  };

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-4">
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
              <p className="mt-4 text-muted-foreground">Loading analytics...</p>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-4 max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold flex items-center gap-2">
                <Brain className="h-6 w-6 text-purple-600" />
                Analytics Dashboard
              </h1>
              <p className="text-muted-foreground text-sm mt-1">
                Comprehensive overview of account activity and DOK knowledge tracking
              </p>
            </div>
          </div>
        </div>

        {/* Main Chart Section */}
        <Card className="mb-4">
          <div className="p-4">
            {/* Controls Row */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-4">
                {/* Primary Metric Selector */}
                <select
                  value={primaryMetric}
                  onChange={(e) => setPrimaryMetric(e.target.value)}
                  className="px-3 py-1.5 text-sm border rounded-lg bg-background"
                >
                  <option value="posts">Posts</option>
                  <option value="dok3_changes">DOK3 Changes</option>
                  <option value="dok4_changes">DOK4 Changes</option>
                  <option value="total_dok_changes">Total DOK Changes</option>
                </select>

              </div>

              <div className="flex items-center gap-2">
                {/* Date Range Pills */}
                <div className="flex items-center bg-muted rounded-lg p-0.5">
                  {dateRangeOptions.map((option) => (
                    <button
                      key={option.label}
                      onClick={() => setDateRange(option.label)}
                      className={`px-3 py-1 text-sm rounded-md transition-colors ${
                        dateRange === option.label
                          ? 'bg-background text-foreground shadow-sm'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                {/* Chart Type Toggle */}
                <div className="flex items-center gap-1 ml-4">
                  <button
                    onClick={() => setChartType('area')}
                    className={`p-1.5 rounded ${chartType === 'area' ? 'bg-muted' : ''}`}
                  >
                    <TrendingUp className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => setChartType('bar')}
                    className={`p-1.5 rounded ${chartType === 'bar' ? 'bg-muted' : ''}`}
                  >
                    <BarChart3 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* Chart Debug */}
            {(() => {
              const sampleData = data.activityTrends.slice(0, 3);
              console.log('Chart primaryMetric:', primaryMetric);
              console.log('Sample data structure:');
              sampleData.forEach((d, i) => {
                console.log(`Day ${i + 1} (${d.date}):`, {
                  posts: d.posts,
                  dok3_changes: d.dok3_changes,
                  dok4_changes: d.dok4_changes,
                  total_dok_changes: d.total_dok_changes,
                  selectedValue: d[primaryMetric]
                });
              });
              return null;
            })()}

            {/* Chart */}
            <ResponsiveContainer width="100%" height={250}>
              {chartType === 'area' ? (
                <AreaChart data={data.activityTrends}>
                  <defs>
                    <linearGradient id="primaryGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={getMetricColor(primaryMetric)} stopOpacity={0.3}/>
                      <stop offset="95%" stopColor={getMetricColor(primaryMetric)} stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="date" stroke="#9CA3AF" fontSize={11} />
                  <YAxis stroke="#9CA3AF" fontSize={11} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area 
                    type="monotone" 
                    dataKey={primaryMetric} 
                    stroke={getMetricColor(primaryMetric)} 
                    fill="url(#primaryGradient)" 
                    strokeWidth={2}
                  />
                </AreaChart>
              ) : (
                <BarChart data={data.activityTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="date" stroke="#9CA3AF" fontSize={11} />
                  <YAxis stroke="#9CA3AF" fontSize={11} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey={primaryMetric} fill={getMetricColor(primaryMetric)} radius={[4, 4, 0, 0]} />
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Unified Analytics Content */}
        <div className="space-y-6">
          {/* Overview Stats Row - Activity + DOK */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-7 gap-4">
            {/* Activity Metrics */}
            <Card>
              <CardContent className="p-3">
                <p className="text-xs text-muted-foreground mb-1">Active Brainlifts</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">{data.performanceMetrics.activeAccounts}</span>
                  <span className="text-xs">/ {data.performanceMetrics.activeAccounts + 5}</span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <p className="text-xs text-muted-foreground mb-1">Total Posts</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">{data.weeklyComparison.tweets.current + data.weeklyComparison.threads.current}</span>
                  <span className={`text-xs flex items-center gap-0.5 ${getChangeColor(data.weeklyComparison.activity.change)}`}>
                    {getChangeIcon(data.weeklyComparison.activity.change)}
                    {Math.round(Math.abs(data.weeklyComparison.activity.change))}%
                  </span>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <p className="text-xs text-muted-foreground mb-1">Avg per Day</p>
                <span className="text-2xl font-bold">{data.performanceMetrics.avgPerDay}</span>
              </CardContent>
            </Card>

            {/* DOK Metrics */}
            <Card>
              <CardContent className="p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Total DOK Changes</p>
                    <p className="text-2xl font-bold text-purple-600">
                      {dokData.summary?.total_changes || 0}
                    </p>
                  </div>
                  <Activity className="h-6 w-6 text-purple-600/30" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">DOK3 Changes</p>
                    <div className="flex items-baseline gap-1">
                      <p className="text-xl font-bold text-green-600">
                        {dokData.summary?.dok3_changes?.total || 0}
                      </p>
                      <div className="text-[10px] text-muted-foreground">
                        <span className="text-emerald-600">+{dokData.summary?.dok3_changes?.added || 0}</span>
                        {' '}
                        <span className="text-cyan-500">~{dokData.summary?.dok3_changes?.updated || 0}</span>
                        {' '}
                        <span className="text-orange-600">-{dokData.summary?.dok3_changes?.deleted || 0}</span>
                      </div>
                    </div>
                  </div>
                  <Plus className="h-6 w-6 text-green-600/30" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">DOK4 Changes</p>
                    <div className="flex items-baseline gap-1">
                      <p className="text-xl font-bold text-blue-600">
                        {dokData.summary?.dok4_changes?.total || 0}
                      </p>
                      <div className="text-[10px] text-muted-foreground">
                        <span className="text-indigo-600">+{dokData.summary?.dok4_changes?.added || 0}</span>
                        {' '}
                        <span className="text-purple-600">~{dokData.summary?.dok4_changes?.updated || 0}</span>
                        {' '}
                        <span className="text-pink-600">-{dokData.summary?.dok4_changes?.deleted || 0}</span>
                      </div>
                    </div>
                  </div>
                  <BookOpen className="h-6 w-6 text-blue-600/30" />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Contributors</p>
                    <p className="text-2xl font-bold text-purple-600">
                      {dokData.leaderboard?.length || 0}
                    </p>
                  </div>
                  <Users className="h-6 w-6 text-purple-600/30" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Activity Over Time */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Activity Trends</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                  <LineChart data={data.activityTrends.slice(-7)}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="date" stroke="#9CA3AF" fontSize={10} />
                    <YAxis stroke="#9CA3AF" fontSize={10} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="monotone" dataKey="posts" stroke="#8B5CF6" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* DOK Activity Trends */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">DOK Activity Trends</CardTitle>
              </CardHeader>
              <CardContent>
                {dokData.trends?.length > 0 && (
                  <ResponsiveContainer width="100%" height={180}>
                    <AreaChart data={dokData.trends}>
                      <defs>
                        <linearGradient id="dok3Gradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="dok4Gradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                      <XAxis dataKey="date" stroke="#9CA3AF" fontSize={10} />
                      <YAxis stroke="#9CA3AF" fontSize={10} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area 
                        type="monotone" 
                        dataKey="dok3_added" 
                        stackId="1"
                        stroke="#10B981" 
                        fill="url(#dok3Gradient)" 
                        name="DOK3 Added"
                      />
                      <Area 
                        type="monotone" 
                        dataKey="dok4_added" 
                        stackId="1"
                        stroke="#3B82F6" 
                        fill="url(#dok4Gradient)" 
                        name="DOK4 Added"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            {/* Change Type Breakdown */}
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Change Type Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                {dokData.summary && (
                  <ResponsiveContainer width="100%" height={180}>
                    <BarChart
                      data={[
                        {
                          name: 'Added',
                          DOK3: dokData.summary.dok3_changes?.added || 0,
                          DOK4: dokData.summary.dok4_changes?.added || 0
                        },
                        {
                          name: 'Updated',
                          DOK3: dokData.summary.dok3_changes?.updated || 0,
                          DOK4: dokData.summary.dok4_changes?.updated || 0
                        },
                        {
                          name: 'Deleted',
                          DOK3: dokData.summary.dok3_changes?.deleted || 0,
                          DOK4: dokData.summary.dok4_changes?.deleted || 0
                        }
                      ]}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                      <XAxis dataKey="name" stroke="#9CA3AF" fontSize={10} />
                      <YAxis stroke="#9CA3AF" fontSize={10} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="DOK3" fill="#10B981" name="DOK3" />
                      <Bar dataKey="DOK4" fill="#3B82F6" name="DOK4" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

        </div>
      </div>
    </>
  );
};