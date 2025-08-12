import { apiClient } from './api';
import { useNotificationStore } from '../store/useNotificationStore';
import { Tweet, Thread } from '../types';

interface FollowerUpdate {
  accountId: number;
  accountUsername: string;
  followerUsername: string;
  followerDisplayName?: string;
  followerProfilePic?: string;
  approvedAt: string;
}

class NotificationPoller {
  private intervalId: NodeJS.Timeout | null = null;
  private lastCheckedTime: Date = new Date();
  private seenTweetIds = new Set<number>();
  private seenThreadIds = new Set<string>();
  private seenFollowerUpdates = new Set<string>();
  private isFirstLoad = true;

  start() {
    // Initial load - mark all existing as seen without notifying
    this.loadInitialData();
    
    // Start polling every 30 seconds
    this.intervalId = setInterval(() => {
      this.checkForNewPosts();
    }, 30000);

    // Also check immediately after initial load
    setTimeout(() => {
      this.isFirstLoad = false;
      this.checkForNewPosts();
    }, 2000);
  }

  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  private async loadInitialData() {
    try {
      const [tweets, threads, accounts] = await Promise.all([
        apiClient.getTweets(),
        apiClient.getThreads(),
        apiClient.getAccounts()
      ]);

      // Mark all existing tweets and threads as seen
      tweets.forEach((tweet: Tweet) => {
        if (tweet.status === 'posted') {
          this.seenTweetIds.add(tweet.id);
        }
      });

      threads.forEach((thread: Thread) => {
        if (thread.posted_count > 0) {
          this.seenThreadIds.add(thread.thread_id);
        }
      });

      // Mark all existing followers as seen
      for (const account of accounts) {
        try {
          const followersData = await apiClient.getSavedFollowers(account.id, 1, 100);
          if (followersData.followers) {
            followersData.followers.forEach((follower: any) => {
              const key = `${account.username}-${follower.username}`;
              this.seenFollowerUpdates.add(key);
            });
          }
        } catch (error) {
          // Silently continue if account has no followers
        }
      }

      // Update last checked time to now
      this.lastCheckedTime = new Date();
    } catch (error) {
      console.error('Failed to load initial data:', error);
    }
  }

  private async checkForNewPosts() {
    if (this.isFirstLoad) return;

    try {
      const [tweets, threads, accounts] = await Promise.all([
        apiClient.getTweets(),
        apiClient.getThreads(),
        apiClient.getAccounts()
      ]);

      // Check for new posted tweets
      const postedTweets = tweets.filter((tweet: Tweet) => 
        tweet.status === 'posted' && 
        !this.seenTweetIds.has(tweet.id) &&
        tweet.postedAt && 
        new Date(tweet.postedAt) > this.lastCheckedTime
      );

      // Check for new posted threads
      const postedThreads = threads.filter((thread: Thread) => 
        thread.posted_count > 0 && 
        !this.seenThreadIds.has(thread.thread_id) &&
        new Date(thread.created_at) > this.lastCheckedTime
      );

      // Check for new followers (limit to 4 most recent)
      const newFollowerUpdates: FollowerUpdate[] = [];
      for (const account of accounts.slice(0, 10)) { // Check first 10 accounts for performance
        try {
          const followersData = await apiClient.getSavedFollowers(account.id, 1, 20);
          if (followersData.followers) {
            for (const follower of followersData.followers) {
              const key = `${account.username}-${follower.username}`;
              if (!this.seenFollowerUpdates.has(key)) {
                newFollowerUpdates.push({
                  accountId: account.id,
                  accountUsername: account.username,
                  followerUsername: follower.username,
                  followerDisplayName: follower.display_name,
                  followerProfilePic: follower.profile_picture,
                  approvedAt: follower.approved_at || new Date().toISOString()
                });
                this.seenFollowerUpdates.add(key);
              }
            }
          }
        } catch (error) {
          // Silently continue
        }
      }

      // Sort by approved_at date and take only the 4 most recent
      const recentFollowerUpdates = newFollowerUpdates
        .sort((a, b) => new Date(b.approvedAt).getTime() - new Date(a.approvedAt).getTime())
        .slice(0, 4);

      // Create notifications for new tweets
      postedTweets.forEach((tweet: Tweet) => {
        const account = accounts.find(a => a.username === tweet.username);
        
        useNotificationStore.getState().addNotification({
          type: 'success',
          title: 'New Post Published',
          message: `@${tweet.username} just posted a change`,
          accountUsername: tweet.username,
          accountProfilePic: account?.profilePicture,
          tweetContent: tweet.content.length > 100 
            ? tweet.content.substring(0, 100) + '...' 
            : tweet.content,
        });

        this.seenTweetIds.add(tweet.id);
      });

      // Create notifications for new threads
      postedThreads.forEach((thread: Thread) => {
        const account = accounts.find(a => a.username === thread.account_username);
        
        useNotificationStore.getState().addNotification({
          type: 'success',
          title: 'New Thread Published',
          message: `@${thread.account_username} posted a thread with ${thread.posted_count} tweets`,
          accountUsername: thread.account_username,
          accountProfilePic: account?.profilePicture,
          threadId: thread.thread_id,
          tweetCount: thread.posted_count,
        });

        this.seenThreadIds.add(thread.thread_id);
      });

      // Create notifications for new followers
      recentFollowerUpdates.forEach((update) => {
        const account = accounts.find(a => a.id === update.accountId);
        
        useNotificationStore.getState().addNotification({
          type: 'follower',
          title: 'New Follower',
          message: `@${update.followerUsername} followed @${update.accountUsername}`,
          accountUsername: update.accountUsername,
          accountProfilePic: account?.profilePicture,
          followerUsername: update.followerUsername,
          followerDisplayName: update.followerDisplayName,
          followerProfilePic: update.followerProfilePic,
        });
      });

      // Update last checked time
      if (postedTweets.length > 0 || postedThreads.length > 0 || recentFollowerUpdates.length > 0) {
        this.lastCheckedTime = new Date();
      }
    } catch (error) {
      console.error('Failed to check for new posts:', error);
    }
  }
}

export const notificationPoller = new NotificationPoller();