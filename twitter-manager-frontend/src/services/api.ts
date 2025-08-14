import axios, { AxiosInstance, AxiosError } from 'axios';
import { ApiResponse, TwitterAccount, Tweet, TokenHealth, BatchPostRequest, TwitterList, Thread } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5555/api/v1';
const API_KEY = import.meta.env.VITE_API_KEY || '';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY,
      },
    });

    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          console.error('API Key is invalid or missing');
        }
        return Promise.reject(error);
      }
    );
  }

  // Account Management
  async getAccounts(): Promise<TwitterAccount[]> {
    const { data } = await this.client.get<{ accounts: any[], total: number }>('/accounts');
    // Map backend response to frontend TwitterAccount interface
    return (data.accounts || []).map(account => ({
      id: account.id,
      username: account.username,
      displayName: account.display_name,
      profilePicture: account.profile_picture,
      accountType: account.account_type,
      authorized: account.status === 'active',
      followerCount: account.followerCount || account.follower_count,
      tweetCount: account.tweet_count,
      threadCount: account.thread_count,
      createdAt: account.created_at,
      lastActiveAt: account.last_active_at,
      tokenExpiresAt: account.token_expires_at,
      tokenRefreshFailures: account.token_refresh_failures,
      tokenStatus: account.token_status || (account.status === 'active' ? 'healthy' : 'expired'),
    }));
  }

  async getAccount(id: number): Promise<TwitterAccount> {
    const { data } = await this.client.get<any>(`/accounts/${id}`);
    if (!data || !data.account) throw new Error('Account not found');
    // Map backend response to frontend TwitterAccount interface
    const account = data.account;
    return {
      id: account.id,
      username: account.username,
      displayName: account.display_name,
      profilePicture: account.profile_picture,
      accountType: account.account_type || 'managed',
      authorized: account.status === 'active',
      followerCount: account.follower_count,
      followingCount: account.following_count,
      tweetCount: data.stats?.standalone_tweets || data.stats?.total_tweets || account.tweet_count || 0,
      threadCount: data.stats?.total_threads || 0,
      threadTweetCount: data.stats?.thread_tweets || 0,
      createdAt: account.created_at,
      lastActiveAt: account.last_active_at,
      tokenExpiresAt: account.token_expires_at,
      tokenRefreshFailures: account.token_refresh_failures || account.refresh_failure_count,
      tokenStatus: account.token_health || account.token_status || (account.status === 'active' ? 'healthy' : 'expired'),
      verified: account.verified,
      description: account.description,
      twitterUserId: account.twitter_user_id,
      workflowyUrl: account.workflowy_url,
      stats: data.stats ? {
        standalone_tweets: data.stats.standalone_tweets,
        thread_tweets: data.stats.thread_tweets,
        total_threads: data.stats.total_threads,
        pending_standalone: data.stats.pending_standalone,
        posted_standalone: data.stats.posted_standalone,
        failed_standalone: data.stats.failed_standalone,
        pending_threads: data.stats.pending_threads,
        posted_threads: data.stats.posted_threads,
      } : undefined,
    };
  }
  
  async getAccountFollowers(id: number, paginationToken?: string, maxResults: number = 20): Promise<{
    followers: Array<{
      id: string;
      username: string;
      name: string;
      profile_image_url?: string;
      description?: string;
      verified: boolean;
      followers_count: number;
      following_count: number;
      tweet_count: number;
      created_at: string;
    }>;
    pagination: {
      next_token?: string;
      previous_token?: string;
      result_count: number;
    };
    total_count: number;
  }> {
    const params: any = { max_results: maxResults };
    if (paginationToken) {
      params.pagination_token = paginationToken;
    }
    
    const { data } = await this.client.get(`/accounts/${id}/followers`, { params });
    return data;
  }

  async getSavedFollowers(id: number, page: number = 1, perPage: number = 20): Promise<{
    account: {
      id: number;
      username: string;
    };
    followers: Array<{
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
    }>;
    pagination: {
      page: number;
      per_page: number;
      total: number;
      pages: number;
    };
  }> {
    const { data } = await this.client.get(`/accounts/${id}/saved-followers`, {
      params: { page, per_page: perPage }
    });
    return data;
  }

  async saveSingleFollower(accountId: number, follower: {
    twitter_user_id: string;
    username: string;
    display_name: string;
    profile_picture?: string;
    description?: string;
    verified: boolean;
    followers_count: number;
    following_count: number;
    tweet_count: number;
    is_approved: boolean;
  }): Promise<void> {
    await this.client.post(`/accounts/${accountId}/saved-followers`, follower);
  }

  async removeSavedFollower(accountId: number, followerId: string): Promise<void> {
    await this.client.delete(`/accounts/${accountId}/saved-followers/${followerId}`);
  }

  async deleteAccount(id: number): Promise<void> {
    await this.client.delete(`/accounts/${id}`);
  }

  async refreshToken(id: number): Promise<TwitterAccount> {
    const { data } = await this.client.post<ApiResponse<TwitterAccount>>(`/accounts/${id}/refresh-token`);
    if (!data.data) throw new Error('Failed to refresh token');
    return data.data;
  }

  async clearTokenFailures(id: number): Promise<void> {
    await this.client.post(`/accounts/${id}/clear-failures`);
  }

  async getTokenHealth(): Promise<TokenHealth[]> {
    const { data } = await this.client.get<ApiResponse<TokenHealth[]>>('/accounts/token-health');
    return data.data || [];
  }

  async refreshAllTokens(): Promise<{ refreshed: number; failed: number }> {
    const { data } = await this.client.post<ApiResponse<{ refreshed: number; failed: number }>>('/accounts/refresh-tokens');
    return data.data || { refreshed: 0, failed: 0 };
  }

  // Tweet Management
  async getTweets(accountId?: number, status?: string): Promise<Tweet[]> {
    const params = new URLSearchParams();
    if (accountId) params.append('account_id', accountId.toString());
    if (status) params.append('status', status);
    
    const { data } = await this.client.get<{ tweets: any[], total: number }>(`/tweets?${params}`);
    // Map backend response to frontend Tweet interface
    return (data.tweets || []).map(tweet => ({
      id: tweet.id,
      accountId: tweet.account_id || 0, // Backend doesn't return account_id in list view
      content: tweet.text || tweet.content,
      status: tweet.status,
      tweetId: tweet.tweet_id,
      threadId: tweet.thread_id,
      error: tweet.error,
      createdAt: tweet.created_at,
      postedAt: tweet.posted_at,
      username: tweet.username, // Add username for filtering
    }));
  }

  async createTweet(accountId: number, content: string): Promise<Tweet> {
    const { data } = await this.client.post<ApiResponse<Tweet>>('/tweet', {
      account_id: accountId,
      content,
    });
    if (!data.data) throw new Error('Failed to create tweet');
    return data.data;
  }

  async postTweet(tweetId: number): Promise<Tweet> {
    const { data } = await this.client.post<ApiResponse<Tweet>>(`/tweet/${tweetId}/post`);
    if (!data.data) throw new Error('Failed to post tweet');
    return data.data;
  }

  async deleteTweet(tweetId: number): Promise<void> {
    await this.client.delete(`/tweet/${tweetId}`);
  }

  async batchPost(request: BatchPostRequest): Promise<{ posted: number; failed: number }> {
    const { data } = await this.client.post<ApiResponse<{ posted: number; failed: number }>>('/tweets/batch-post', request);
    return data.data || { posted: 0, failed: 0 };
  }

  // List Management
  async getLists(ownerId?: number): Promise<TwitterList[]> {
    const params = ownerId ? `?owner_id=${ownerId}` : '';
    const { data } = await this.client.get<ApiResponse<TwitterList[]>>(`/lists${params}`);
    return data.data || [];
  }

  async createList(ownerId: number, name: string, description?: string): Promise<TwitterList> {
    const { data } = await this.client.post<ApiResponse<TwitterList>>('/lists', {
      owner_id: ownerId,
      name,
      description,
    });
    if (!data.data) throw new Error('Failed to create list');
    return data.data;
  }

  async deleteList(listId: string): Promise<void> {
    await this.client.delete(`/lists/${listId}`);
  }

  async addToList(listId: string, accountIds: number[]): Promise<void> {
    await this.client.post(`/lists/${listId}/members`, { account_ids: accountIds });
  }

  async removeFromList(listId: string, accountIds: number[]): Promise<void> {
    await this.client.delete(`/lists/${listId}/members`, { data: { account_ids: accountIds } });
  }

  // OAuth
  async getAuthUrl(): Promise<string> {
    const { data } = await this.client.get<ApiResponse<{ auth_url: string }>>('/auth/twitter');
    if (!data.data?.auth_url) throw new Error('Failed to get auth URL');
    return data.data.auth_url;
  }

  // Mock Mode
  async getMockMode(): Promise<boolean> {
    const { data } = await this.client.get<ApiResponse<{ mock_mode: boolean }>>('/mock-mode');
    return data.data?.mock_mode || false;
  }

  async setMockMode(enabled: boolean): Promise<void> {
    await this.client.post('/mock-mode', { enabled });
  }

  // Thread Management
  async getThreads(accountId?: number): Promise<Thread[]> {
    const { data } = await this.client.get<{ threads: Thread[] }>('/threads');
    const allThreads = data.threads || [];
    
    // If accountId is provided, we need to filter by the account's username
    if (accountId) {
      // First, get the account to know its username
      const account = await this.getAccount(accountId);
      // Filter threads by account_username
      return allThreads.filter(thread => thread.account_username === account.username);
    }
    
    return allThreads;
  }

  async getThreadDetails(threadId: string): Promise<Thread> {
    const { data } = await this.client.get<Thread>(`/thread/${threadId}`);
    return data;
  }

  // Brainlift Activity Rankings
  async getUserActivityRankings(): Promise<{
    rankings: Array<{
      rank: number;
      id: number;
      username: string;
      displayName: string;
      profilePicture: string;
      tweetCount: number;
      postedCount: number;
      pendingCount: number;
      failedCount: number;
    }>;
    timestamp: string;
  }> {
    const { data } = await this.client.get('/user-activity-rankings');
    return data;
  }

  // Sync account profiles from Twitter
  async syncAccountProfiles(): Promise<{
    message: string;
    results: {
      synced: Array<{
        username: string;
        display_name: string;
        profile_picture: string;
      }>;
      failed: Array<{
        username: string;
        error: string;
      }>;
      total: number;
    };
  }> {
    const { data } = await this.client.post('/accounts/sync-profiles', {});
    return data;
  }

  // Get accounts grouped by lists
  async getAccountsByLists(): Promise<{
    lists: Array<{
      id: string;
      list_id: string;
      name: string;
      description: string;
      mode: string;
      source: string;
      is_managed: boolean;
      owner_username: string;
      last_synced_at: string | null;
      member_count: number;
      members: TwitterAccount[];
    }>;
    unassigned_accounts: TwitterAccount[];
    stats: {
      total_lists: number;
      total_managed_accounts: number;
      accounts_in_lists: number;
      accounts_not_in_lists: number;
    };
  }> {
    const { data } = await this.client.get('/accounts/by-lists');
    return data;
  }
}

export const apiClient = new ApiClient();