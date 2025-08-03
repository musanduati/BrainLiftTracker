import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Calendar, MessageSquare, Heart, Repeat2, Share, MoreHorizontal } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import { TwitterAccount, Tweet } from '../types';
import { formatDistanceToNow } from 'date-fns';
import toast from 'react-hot-toast';

export const AccountDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [account, setAccount] = useState<TwitterAccount | null>(null);
  const [tweets, setTweets] = useState<Tweet[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingTweets, setLoadingTweets] = useState(true);

  useEffect(() => {
    if (id) {
      loadAccountData(parseInt(id));
    }
  }, [id]);

  const loadAccountData = async (accountId: number) => {
    try {
      setLoading(true);
      setLoadingTweets(true);

      // Load account details
      const accountData = await apiClient.getAccount(accountId);
      setAccount(accountData);

      // Load tweets for this account
      const tweetsData = await apiClient.getTweets(accountId, 'posted');
      setTweets(tweetsData.sort((a, b) => 
        new Date(b.postedAt || b.createdAt).getTime() - 
        new Date(a.postedAt || a.createdAt).getTime()
      ));
    } catch (error) {
      toast.error('Failed to load account data');
      console.error('Account detail error:', error);
    } finally {
      setLoading(false);
      setLoadingTweets(false);
    }
  };

  const formatTweetTime = (date: string) => {
    return formatDistanceToNow(new Date(date), { addSuffix: true });
  };

  const renderTweet = (tweet: Tweet) => (
    <Card key={tweet.id} className="hover:bg-muted/50 transition-colors">
      <CardContent className="p-4">
        <div className="flex gap-3">
          {/* Profile Picture */}
          <div className="flex-shrink-0">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white font-semibold">
              {account?.username.charAt(0).toUpperCase()}
            </div>
          </div>

          {/* Tweet Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-1 text-sm">
                <span className="font-semibold">{account?.displayName || account?.username}</span>
                <span className="text-muted-foreground">@{account?.username}</span>
                <span className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">{formatTweetTime(tweet.postedAt || tweet.createdAt)}</span>
              </div>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreHorizontal size={16} />
              </Button>
            </div>

            {/* Tweet Text */}
            <div className="mt-1 text-sm whitespace-pre-wrap break-words">
              {tweet.content}
            </div>

            {/* Engagement Metrics */}
            <div className="mt-3 flex items-center gap-6 text-muted-foreground">
              <button className="flex items-center gap-1 hover:text-blue-500 transition-colors">
                <MessageSquare size={16} />
                <span className="text-xs">{tweet.engagementMetrics?.replies || 0}</span>
              </button>
              <button className="flex items-center gap-1 hover:text-green-500 transition-colors">
                <Repeat2 size={16} />
                <span className="text-xs">{tweet.engagementMetrics?.retweets || 0}</span>
              </button>
              <button className="flex items-center gap-1 hover:text-red-500 transition-colors">
                <Heart size={16} />
                <span className="text-xs">{tweet.engagementMetrics?.likes || 0}</span>
              </button>
              <button className="flex items-center gap-1 hover:text-blue-500 transition-colors">
                <Share size={16} />
              </button>
            </div>

            {/* Tweet Status Badge */}
            {tweet.status === 'failed' && (
              <div className="mt-2">
                <Badge variant="destructive" className="text-xs">
                  Failed: {tweet.error}
                </Badge>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <>
        <TopBar title="Account Details" />
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
        <TopBar title="Account Not Found" />
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
      <TopBar title={`@${account.username}`} />
      
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
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-white text-2xl font-semibold">
                {account.username.charAt(0).toUpperCase()}
              </div>

              {/* Account Info */}
              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">{account.displayName || account.username}</h2>
                    <p className="text-muted-foreground">@{account.username}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={account.authorized ? 'default' : 'secondary'}>
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
                    <span className="font-semibold">{account.tweetCount || tweets.length}</span>
                    <span className="text-muted-foreground ml-1">Tweets</span>
                  </div>
                  <div>
                    <span className="font-semibold">{account.followerCount || 0}</span>
                    <span className="text-muted-foreground ml-1">Followers</span>
                  </div>
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Calendar size={14} />
                    <span>Joined {new Date(account.createdAt).toLocaleDateString()}</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tweets Section */}
        <div>
          <h3 className="text-lg font-semibold mb-4">Tweets ({tweets.length})</h3>
          
          {loadingTweets ? (
            <div className="space-y-4">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </div>
          ) : tweets.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-center text-muted-foreground">
                No tweets posted yet
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {tweets.map(renderTweet)}
            </div>
          )}
        </div>
      </div>
    </>
  );
};