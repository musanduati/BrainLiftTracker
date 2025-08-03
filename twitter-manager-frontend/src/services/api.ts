import axios, { AxiosInstance, AxiosError } from 'axios';
import { ApiResponse, TwitterAccount, Tweet, TokenHealth, BatchPostRequest, TwitterList, PaginatedResponse } from '../types';

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
      followerCount: account.follower_count,
      tweetCount: account.tweet_count,
      createdAt: account.created_at,
      lastActiveAt: account.last_active_at,
      tokenExpiresAt: account.token_expires_at,
      tokenRefreshFailures: account.token_refresh_failures,
      tokenStatus: account.token_status || (account.status === 'active' ? 'healthy' : 'expired'),
    }));
  }

  async getAccount(id: number): Promise<TwitterAccount> {
    const { data } = await this.client.get<any>(`/accounts/${id}`);
    if (!data) throw new Error('Account not found');
    // Map backend response to frontend TwitterAccount interface
    return {
      id: data.id,
      username: data.username,
      displayName: data.display_name,
      profilePicture: data.profile_picture,
      accountType: data.account_type || 'managed',
      authorized: data.status === 'active',
      followerCount: data.follower_count,
      tweetCount: data.tweet_count,
      createdAt: data.created_at,
      lastActiveAt: data.last_active_at,
      tokenExpiresAt: data.token_expires_at,
      tokenRefreshFailures: data.token_refresh_failures,
      tokenStatus: data.token_status || (data.status === 'active' ? 'healthy' : 'expired'),
    };
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
      error: tweet.error,
      createdAt: tweet.created_at,
      postedAt: tweet.posted_at,
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
}

export const apiClient = new ApiClient();