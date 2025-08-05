import { create } from 'zustand';
import { TwitterAccount, Tweet, TwitterList } from '../types';

interface AppState {
  // Theme
  theme: 'light' | 'dark';
  toggleTheme: () => void;

  // View preferences
  accountViewMode: 'grid' | 'list';
  setAccountViewMode: (mode: 'grid' | 'list') => void;

  // Accounts
  accounts: TwitterAccount[];
  selectedAccountIds: number[];
  isLoadingAccounts: boolean;
  setAccounts: (accounts: TwitterAccount[]) => void;
  updateAccount: (id: number, account: Partial<TwitterAccount>) => void;
  removeAccount: (id: number) => void;
  toggleAccountSelection: (id: number) => void;
  selectAllAccounts: () => void;
  clearAccountSelection: () => void;
  setLoadingAccounts: (loading: boolean) => void;

  // Tweets
  tweets: Tweet[];
  isLoadingTweets: boolean;
  setTweets: (tweets: Tweet[]) => void;
  addTweet: (tweet: Tweet) => void;
  updateTweet: (id: number, tweet: Partial<Tweet>) => void;
  removeTweet: (id: number) => void;
  setLoadingTweets: (loading: boolean) => void;

  // Lists
  lists: TwitterList[];
  isLoadingLists: boolean;
  setLists: (lists: TwitterList[]) => void;
  addList: (list: TwitterList) => void;
  removeList: (id: string) => void;
  setLoadingLists: (loading: boolean) => void;

  // Modals
  isComposeTweetModalOpen: boolean;
  openComposeTweetModal: () => void;
  closeComposeTweetModal: () => void;

  // Notifications
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;

  // Mock mode
  isMockMode: boolean;
  setMockMode: (enabled: boolean) => void;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  timestamp: Date;
}

export const useStore = create<AppState>((set) => ({
  // Theme - default to dark if not set
  theme: (localStorage.getItem('theme') as 'light' | 'dark') || 'dark',
  toggleTheme: () => set((state) => {
    const newTheme = state.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('theme', newTheme);
    document.documentElement.classList.toggle('dark', newTheme === 'dark');
    return { theme: newTheme };
  }),

  // View preferences
  accountViewMode: (localStorage.getItem('accountViewMode') as 'grid' | 'list') || 'grid',
  setAccountViewMode: (mode) => {
    localStorage.setItem('accountViewMode', mode);
    set({ accountViewMode: mode });
  },

  // Accounts
  accounts: [],
  selectedAccountIds: [],
  isLoadingAccounts: false,
  setAccounts: (accounts) => set({ accounts }),
  updateAccount: (id, updates) => set((state) => ({
    accounts: state.accounts.map((account) =>
      account.id === id ? { ...account, ...updates } : account
    ),
  })),
  removeAccount: (id) => set((state) => ({
    accounts: state.accounts.filter((account) => account.id !== id),
    selectedAccountIds: state.selectedAccountIds.filter((selectedId) => selectedId !== id),
  })),
  toggleAccountSelection: (id) => set((state) => ({
    selectedAccountIds: state.selectedAccountIds.includes(id)
      ? state.selectedAccountIds.filter((selectedId) => selectedId !== id)
      : [...state.selectedAccountIds, id],
  })),
  selectAllAccounts: () => set((state) => ({
    selectedAccountIds: state.accounts.map((account) => account.id),
  })),
  clearAccountSelection: () => set({ selectedAccountIds: [] }),
  setLoadingAccounts: (loading) => set({ isLoadingAccounts: loading }),

  // Tweets
  tweets: [],
  isLoadingTweets: false,
  setTweets: (tweets) => set({ tweets }),
  addTweet: (tweet) => set((state) => ({ tweets: [tweet, ...state.tweets] })),
  updateTweet: (id, updates) => set((state) => ({
    tweets: state.tweets.map((tweet) =>
      tweet.id === id ? { ...tweet, ...updates } : tweet
    ),
  })),
  removeTweet: (id) => set((state) => ({
    tweets: state.tweets.filter((tweet) => tweet.id !== id),
  })),
  setLoadingTweets: (loading) => set({ isLoadingTweets: loading }),

  // Lists
  lists: [],
  isLoadingLists: false,
  setLists: (lists) => set({ lists }),
  addList: (list) => set((state) => ({ lists: [...state.lists, list] })),
  removeList: (id) => set((state) => ({
    lists: state.lists.filter((list) => list.id !== id),
  })),
  setLoadingLists: (loading) => set({ isLoadingLists: loading }),

  // Modals
  isComposeTweetModalOpen: false,
  openComposeTweetModal: () => set({ isComposeTweetModalOpen: true }),
  closeComposeTweetModal: () => set({ isComposeTweetModalOpen: false }),

  // Notifications
  notifications: [],
  addNotification: (notification) => set((state) => ({
    notifications: [
      ...state.notifications,
      { ...notification, id: Date.now().toString() },
    ],
  })),
  removeNotification: (id) => set((state) => ({
    notifications: state.notifications.filter((notification) => notification.id !== id),
  })),

  // Mock mode
  isMockMode: false,
  setMockMode: (enabled) => set({ isMockMode: enabled }),
}));