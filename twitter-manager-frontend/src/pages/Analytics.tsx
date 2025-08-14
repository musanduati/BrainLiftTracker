import React, { useEffect, useState } from 'react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent } from '../components/common/Card';
import { TrendingUp, BarChart3, ArrowUp, ArrowDown, Minus } from 'lucide-react';
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
  engagementMetrics: any;
}

export const Analytics: React.FC = () => {
  const [data, setData] = useState<AnalyticsData>({
    activityTrends: [],
    performanceMetrics: {},
    topPerformers: [],
    weeklyComparison: {},
    engagementMetrics: {}
  });
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState('7D');
  const [primaryMetric, setPrimaryMetric] = useState('activity');
  const [secondaryMetric, setSecondaryMetric] = useState('none');
  const [chartType, setChartType] = useState('area');

  const dateRangeOptions = [
    { label: '7D', value: 7 },
    { label: '2W', value: 14 },
    { label: '4W', value: 28 },
    { label: '3M', value: 90 },
    { label: '1Y', value: 365 }
  ];

  useEffect(() => {
    loadAnalyticsData();
  }, [dateRange]);

  const loadAnalyticsData = async () => {
    try {
      setLoading(true);
      
      const days = dateRangeOptions.find(opt => opt.label === dateRange)?.value || 7;
      
      const [accounts, lists, tweets, threads] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getAccountsByLists(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      const analyticsData = processAnalyticsData(accounts, lists, tweets, threads, days);
      setData(analyticsData);
      
    } catch (error) {
      toast.error('Failed to load analytics data');
      console.error('Analytics error:', error);
    } finally {
      setLoading(false);
    }
  };

  const processAnalyticsData = (accounts: any[], listsData: any, tweets: any[], threads: any[], days: number): AnalyticsData => {
    const endDate = new Date();
    const startDate = subDays(endDate, days);
    const dateInterval = eachDayOfInterval({ start: startDate, end: endDate });
    
    // Activity Trends
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
        activity: dayTweets.length + dayThreads.length,
        tweets: dayTweets.length,
        threads: dayThreads.length,
        posted: dayTweets.filter(t => t.status === 'posted').length,
        engagement: Math.floor(Math.random() * 100) // Placeholder
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

    const performanceMetrics = {
      totalActivity,
      successRate: totalTweets > 0 ? Math.round((postedTweets / totalTweets) * 100) : 0,
      failureRate: totalTweets > 0 ? Math.round((failedTweets / totalTweets) * 100) : 0,
      activeAccounts: new Set([...tweets.map(t => t.username), ...threads.map(t => t.account_username)]).size,
      postedCount: postedTweets,
      postedChange: Math.round(postedChange),
      pendingCount: pendingTweets,
      pendingChange: Math.round(Math.random() * 20 - 10), // Placeholder
      failedCount: failedTweets,
      failedChange: Math.round(Math.random() * 20 - 10), // Placeholder
      totalLists: listsData.lists ? listsData.lists.length : 0,
      avgPerDay: Math.round(totalActivity / days)
    };

    const weeklyComparison = {
      activity: { current: thisWeekActivity, change: weeklyChange },
      tweets: { 
        current: totalTweets,  // Show total tweets, not just this week
        change: 15 // Placeholder
      },
      threads: {
        current: totalThreads,  // Show total threads, not just this week
        change: -5 // Placeholder
      }
    };

    const engagementMetrics = {
      impressions: Math.floor(Math.random() * 10000),
      impressionsChange: -54,
      engagementRate: 31,
      engagementRateChange: 396,
      engagements: totalActivity,
      engagementsChange: 125,
      profileVisits: Math.floor(Math.random() * 100),
      profileVisitsChange: -100,
      replies: Math.floor(Math.random() * 50),
      repliesChange: 106,
      likes: Math.floor(Math.random() * 200),
      reposts: Math.floor(Math.random() * 50),
      bookmarks: Math.floor(Math.random() * 30),
      shares: Math.floor(Math.random() * 20)
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
      weeklyComparison,
      engagementMetrics
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
          <h1 className="text-2xl font-bold">Analytics</h1>
          <p className="text-muted-foreground text-sm mt-1">Account overview</p>
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
                  <option value="activity">Total Activity</option>
                  <option value="tweets">Tweets</option>
                  <option value="threads">Threads</option>
                  <option value="engagement">Engagement</option>
                </select>

                {/* Secondary Metric Selector */}
                <select
                  value={secondaryMetric}
                  onChange={(e) => setSecondaryMetric(e.target.value)}
                  className="px-3 py-1.5 text-sm border rounded-lg bg-background text-muted-foreground"
                >
                  <option value="none">Select secondary metric</option>
                  <option value="tweets">Tweets</option>
                  <option value="threads">Threads</option>
                  <option value="engagement">Engagement</option>
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

            {/* Chart */}
            <ResponsiveContainer width="100%" height={250}>
              {chartType === 'area' ? (
                <AreaChart data={data.activityTrends}>
                  <defs>
                    <linearGradient id="primaryGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="secondaryGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#EC4899" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#EC4899" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="date" stroke="#9CA3AF" fontSize={11} />
                  <YAxis stroke="#9CA3AF" fontSize={11} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area 
                    type="monotone" 
                    dataKey={primaryMetric} 
                    stroke="#8B5CF6" 
                    fill="url(#primaryGradient)" 
                    strokeWidth={2}
                  />
                  {secondaryMetric !== 'none' && (
                    <Area 
                      type="monotone" 
                      dataKey={secondaryMetric} 
                      stroke="#EC4899" 
                      fill="url(#secondaryGradient)" 
                      strokeWidth={2}
                    />
                  )}
                </AreaChart>
              ) : (
                <BarChart data={data.activityTrends}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="date" stroke="#9CA3AF" fontSize={11} />
                  <YAxis stroke="#9CA3AF" fontSize={11} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey={primaryMetric} fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                  {secondaryMetric !== 'none' && (
                    <Bar dataKey={secondaryMetric} fill="#EC4899" radius={[4, 4, 0, 0]} />
                  )}
                </BarChart>
              )}
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Secondary Charts Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* Activity Over Time */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">Activity over time</h3>
              </div>
              <ResponsiveContainer width="100%" height={120}>
                <LineChart data={data.activityTrends.slice(-7)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="date" stroke="#9CA3AF" fontSize={10} />
                  <YAxis stroke="#9CA3AF" fontSize={10} />
                  <Tooltip content={<CustomTooltip />} />
                  <Line type="monotone" dataKey="activity" stroke="#8B5CF6" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Posts & Threads Bar Chart */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">Posts & Threads</h3>
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
                    Posts
                  </span>
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-pink-500 rounded-full"></div>
                    Threads
                  </span>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={120}>
                <BarChart data={data.activityTrends.slice(-4)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="date" stroke="#9CA3AF" fontSize={10} />
                  <YAxis stroke="#9CA3AF" fontSize={10} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="tweets" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="threads" fill="#EC4899" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Metrics Grid - Single Row */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {/* Active Brainlifts */}
          <Card>
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Active Brainlifts</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">{data.performanceMetrics.activeAccounts}</span>
                <span className="text-xs">/ {data.performanceMetrics.activeAccounts + 5}</span>
              </div>
            </CardContent>
          </Card>

          {/* Total Activity */}
          <Card>
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Total Activity</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">{data.engagementMetrics.engagements}</span>
                <span className={`text-xs flex items-center gap-0.5 ${getChangeColor(data.engagementMetrics.engagementsChange)}`}>
                  {getChangeIcon(data.engagementMetrics.engagementsChange)}
                  {Math.abs(data.engagementMetrics.engagementsChange)}%
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Tweets */}
          <Card>
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Tweets</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">{data.weeklyComparison.tweets.current}</span>
                <span className={`text-xs flex items-center gap-0.5 ${getChangeColor(data.weeklyComparison.tweets.change)}`}>
                  {getChangeIcon(data.weeklyComparison.tweets.change)}
                  {Math.abs(data.weeklyComparison.tweets.change)}%
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Threads */}
          <Card>
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Threads</p>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">{data.weeklyComparison.threads.current}</span>
                <span className={`text-xs flex items-center gap-0.5 ${getChangeColor(data.weeklyComparison.threads.change)}`}>
                  {getChangeIcon(data.weeklyComparison.threads.change)}
                  {Math.abs(data.weeklyComparison.threads.change)}%
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Total Lists */}
          <Card>
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Total Lists</p>
              <span className="text-2xl font-bold">{data.performanceMetrics.totalLists}</span>
            </CardContent>
          </Card>

          {/* Avg per Day */}
          <Card>
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground mb-1">Avg per Day</p>
              <span className="text-2xl font-bold">{data.performanceMetrics.avgPerDay}</span>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
};