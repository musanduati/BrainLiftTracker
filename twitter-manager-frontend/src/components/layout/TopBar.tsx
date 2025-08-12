import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, User, Shield } from 'lucide-react';
import { useStore } from '../../store/useStore';
import { useNotificationStore } from '../../store/useNotificationStore';
import { NotificationDropdown } from '../notifications/NotificationDropdown';
import { ThemeSelector } from '../theme/ThemeSelector';
import { cn } from '../../utils/cn';

export const TopBar: React.FC = () => {
  const { isMockMode } = useStore();
  const { unreadCount } = useNotificationStore();
  const [showNotifications, setShowNotifications] = useState(false);

  return (
    <div className="bg-card border-b border-border px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* App Name */}
          <Link to="/" className="font-bold text-3xl hover:opacity-80 transition-opacity">
            Brainlift Monitor
          </Link>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Mock mode indicator */}
          {isMockMode && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-yellow-100 dark:bg-yellow-900/20">
              <Shield size={16} className="text-yellow-600 dark:text-yellow-400" />
              <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
                Mock Mode
              </span>
            </div>
          )}


          {/* Notifications */}
          <div className="relative">
            <button 
              className="relative p-2 rounded-lg hover:bg-accent transition-colors"
              onClick={() => setShowNotifications(!showNotifications)}
              data-notification-bell
            >
              <Bell size={20} className={cn(unreadCount > 0 && "text-blue-500")} />
              {unreadCount > 0 && (
                <>
                  <span className="absolute top-1 right-1 w-2 h-2 bg-blue-500 rounded-full animate-pulse"></span>
                  <span className="absolute -top-1 -right-1 bg-blue-500 text-white text-xs rounded-full min-w-[20px] h-5 flex items-center justify-center px-1 font-semibold">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                </>
              )}
            </button>
            <NotificationDropdown 
              isOpen={showNotifications} 
              onClose={() => setShowNotifications(false)} 
            />
          </div>

          {/* Theme selector */}
          <ThemeSelector />

          {/* User menu */}
          <button className="flex items-center gap-2 p-2 rounded-lg hover:bg-accent transition-colors">
            <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
              <User size={16} className="text-primary-foreground" />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};