export interface TwitterAccount {
  id: number;
  username: string;
  displayName?: string;
  profilePicture?: string;
  accountType: 'managed' | 'list_owner';
  authorized: boolean;
  followerCount?: number;
  followingCount?: number;
  tweetCount?: number;  // Standalone tweets (changes not in threads)
  threadCount?: number;  // Number of threads
  threadTweetCount?: number;  // Number of tweets that are part of threads
  postCount?: number;  // Total posts (tweets + threads combined)
  createdAt: string;
  lastActiveAt?: string;
  tokenExpiresAt?: string;
  tokenRefreshFailures?: number;
  tokenStatus?: 'healthy' | 'expiring' | 'expired' | 'refresh_failed';
  listNames?: string[]; // Optional list of lists this account belongs to
  verified?: boolean;
  description?: string;
  twitterUserId?: string;
  workflowyUrl?: string;
  stats?: {  // Detailed stats from API
    standalone_tweets: number;
    thread_tweets: number;
    total_threads: number;
    pending_standalone: number;
    posted_standalone: number;
    failed_standalone: number;
    pending_threads: number;
    posted_threads: number;
  };
}

export interface Tweet {
  id: number;
  accountId: number;
  content: string;
  status: 'pending' | 'posted' | 'failed';
  tweetId?: string;
  threadId?: string;
  error?: string;
  createdAt: string;
  postedAt?: string;
  username?: string; // Added for filtering
  engagementMetrics?: {
    likes: number;
    retweets: number;
    replies: number;
    views: number;
  };
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface TokenHealth {
  accountId: number;
  username: string;
  expiresAt: string;
  status: 'healthy' | 'expiring_soon' | 'expired' | 'refresh_failed';
  refreshFailures: number;
  lastRefreshAttempt?: string;
}

export interface BatchPostRequest {
  accountIds: number[];
  content: string;
  scheduledFor?: string;
}

export interface TwitterList {
  id: string;
  name: string;
  description?: string;
  memberCount: number;
  ownerId: number;
  createdAt: string;
}

export interface ListMembership {
  listId: string;
  accountId: number;
  addedAt: string;
}

export interface ThreadTweet {
  id: number;
  content: string;
  status: 'pending' | 'posted' | 'failed';
  twitter_id?: string;
  reply_to_tweet_id?: string;
  position: number;
  created_at: string;
  posted_at?: string;
  error?: string;
}

export interface Thread {
  thread_id: string;
  account_id: number;
  account_username: string;
  tweet_count: number;
  posted_count: number;
  pending_count: number;
  failed_count: number;
  created_at: string;
  tweets?: ThreadTweet[];
}