export interface TwitterAccount {
  id: number;
  username: string;
  displayName?: string;
  profilePicture?: string;
  accountType: 'managed' | 'list_owner';
  authorized: boolean;
  followerCount?: number;
  tweetCount?: number;
  createdAt: string;
  lastActiveAt?: string;
  tokenExpiresAt?: string;
  tokenRefreshFailures?: number;
  tokenStatus?: 'healthy' | 'expiring' | 'expired' | 'refresh_failed';
}

export interface Tweet {
  id: number;
  accountId: number;
  content: string;
  status: 'pending' | 'posted' | 'failed';
  tweetId?: string;
  error?: string;
  createdAt: string;
  postedAt?: string;
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