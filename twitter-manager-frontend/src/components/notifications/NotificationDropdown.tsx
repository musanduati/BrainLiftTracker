import React, { useRef, useEffect } from 'react';
import { Bell, X, CheckCircle, XCircle, AlertCircle, Info, Trash2, Check, UserPlus } from 'lucide-react';
import { useNotificationStore } from '../../store/useNotificationStore';
import { formatDistanceToNow } from 'date-fns';
import { cn } from '../../utils/cn';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { getAvatarColor, getAvatarText } from '../../utils/avatar';

interface NotificationDropdownProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NotificationDropdown: React.FC<NotificationDropdownProps> = ({ isOpen, onClose }) => {
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { 
    notifications, 
    unreadCount, 
    markAsRead, 
    markAllAsRead, 
    removeNotification, 
    clearAll 
  } = useNotificationStore();

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        const bellButton = document.querySelector('[data-notification-bell]');
        if (bellButton && !bellButton.contains(event.target as Node)) {
          onClose();
        }
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, onClose]);

  const getIcon = (type: string) => {
    switch (type) {
      case 'success':
        return <CheckCircle size={16} className="text-green-500" />;
      case 'error':
        return <XCircle size={16} className="text-red-500" />;
      case 'warning':
        return <AlertCircle size={16} className="text-yellow-500" />;
      case 'follower':
        return <UserPlus size={16} className="text-purple-500" />;
      default:
        return <Info size={16} className="text-blue-500" />;
    }
  };

  const handleNotificationClick = (notification: any) => {
    if (!notification.read) {
      markAsRead(notification.id);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      ref={dropdownRef}
      className="absolute top-full right-0 mt-2 w-96 bg-background border border-border rounded-lg shadow-xl z-50 max-h-[600px] flex flex-col"
    >
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">Notifications</h3>
          {unreadCount > 0 && (
            <Badge variant="default" className="px-2 py-0.5 text-xs">
              {unreadCount} new
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          {notifications.length > 0 && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={markAllAsRead}
                className="p-1.5"
                title="Mark all as read"
              >
                <Check size={16} />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAll}
                className="p-1.5"
                title="Clear all"
              >
                <Trash2 size={16} />
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="p-1.5"
          >
            <X size={16} />
          </Button>
        </div>
      </div>

      {/* Notifications List */}
      <div className="flex-1 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <Bell size={48} className="mx-auto mb-3 opacity-20" />
            <p className="text-sm">No notifications yet</p>
            <p className="text-xs mt-1">Posting updates will appear here</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className={cn(
                  "p-4 hover:bg-muted/30 transition-colors cursor-pointer relative",
                  !notification.read && "bg-blue-50/5"
                )}
                onClick={() => handleNotificationClick(notification)}
              >
                {/* Unread indicator */}
                {!notification.read && (
                  <div className="absolute left-1 top-1/2 -translate-y-1/2 w-2 h-2 bg-blue-500 rounded-full" />
                )}

                <div className="flex gap-3">
                  {/* Account Avatar or Icon */}
                  <div className="flex-shrink-0">
                    {notification.type === 'follower' && notification.followerProfilePic ? (
                      <div className="relative">
                        <img 
                          src={notification.followerProfilePic}
                          alt={notification.followerUsername}
                          className="w-10 h-10 rounded-full object-cover"
                        />
                        <div className="absolute -bottom-1 -right-1 bg-background rounded-full p-0.5">
                          <UserPlus size={12} className="text-purple-500" />
                        </div>
                      </div>
                    ) : notification.accountProfilePic ? (
                      <img 
                        src={notification.accountProfilePic}
                        alt={notification.accountUsername}
                        className="w-10 h-10 rounded-full object-cover"
                      />
                    ) : notification.accountUsername ? (
                      <div className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-sm bg-gradient-to-br",
                        getAvatarColor(notification.accountUsername)
                      )}>
                        {getAvatarText(notification.accountUsername)}
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                        {getIcon(notification.type)}
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          {getIcon(notification.type)}
                          <p className="font-medium text-sm">{notification.title}</p>
                        </div>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {notification.message}
                        </p>
                        
                        {/* Tweet Preview */}
                        {notification.tweetContent && (
                          <div className="mt-2 p-2 bg-muted/50 rounded text-xs text-muted-foreground line-clamp-2">
                            {notification.tweetContent}
                          </div>
                        )}

                        {/* Metadata */}
                        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                          {notification.type === 'follower' ? (
                            <>
                              <span className="font-medium text-purple-600">@{notification.followerUsername}</span>
                              <span>→</span>
                              <span className="font-medium">@{notification.accountUsername}</span>
                              <span>•</span>
                            </>
                          ) : notification.accountUsername && (
                            <>
                              <span>@{notification.accountUsername}</span>
                              <span>•</span>
                            </>
                          )}
                          <span>
                            {formatDistanceToNow(notification.timestamp, { addSuffix: true })}
                          </span>
                          {notification.tweetCount && notification.tweetCount > 1 && (
                            <>
                              <span>•</span>
                              <Badge variant="secondary" className="text-xs px-1 py-0">
                                {notification.tweetCount} tweets
                              </Badge>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Remove button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeNotification(notification.id);
                        }}
                        className="p-1 hover:bg-muted rounded opacity-0 hover:opacity-100 transition-opacity"
                      >
                        <X size={14} className="text-muted-foreground" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      {notifications.length > 10 && (
        <div className="p-3 border-t border-border text-center">
          <p className="text-xs text-muted-foreground">
            Showing {notifications.length} notifications
          </p>
        </div>
      )}
    </div>
  );
};