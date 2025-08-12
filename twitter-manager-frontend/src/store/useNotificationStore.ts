import { create } from 'zustand';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning' | 'follower';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  accountUsername?: string;
  accountProfilePic?: string;
  tweetContent?: string;
  threadId?: string;
  tweetCount?: number;
  followerUsername?: string;
  followerProfilePic?: string;
  followerDisplayName?: string;
}

interface NotificationStore {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  unreadCount: 0,

  addNotification: (notification) => {
    const newNotification: Notification = {
      ...notification,
      id: Date.now().toString(),
      timestamp: new Date(),
      read: false,
    };

    set((state) => ({
      notifications: [newNotification, ...state.notifications].slice(0, 50), // Keep last 50 notifications
      unreadCount: state.unreadCount + 1,
    }));

    // Auto-remove after 24 hours
    setTimeout(() => {
      set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== newNotification.id),
      }));
    }, 24 * 60 * 60 * 1000);
  },

  markAsRead: (id) => {
    set((state) => {
      const notification = state.notifications.find((n) => n.id === id);
      if (notification && !notification.read) {
        return {
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
          unreadCount: Math.max(0, state.unreadCount - 1),
        };
      }
      return state;
    });
  },

  markAllAsRead: () => {
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }));
  },

  removeNotification: (id) => {
    set((state) => {
      const notification = state.notifications.find((n) => n.id === id);
      return {
        notifications: state.notifications.filter((n) => n.id !== id),
        unreadCount: notification && !notification.read 
          ? Math.max(0, state.unreadCount - 1) 
          : state.unreadCount,
      };
    });
  },

  clearAll: () => {
    set(() => ({
      notifications: [],
      unreadCount: 0,
    }));
  },
}));