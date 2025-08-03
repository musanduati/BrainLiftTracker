import React from 'react';
import { MoreVertical, RefreshCw, MessageSquare, CheckCircle, AlertCircle } from 'lucide-react';
import { TwitterAccount } from '../../types';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { formatNumber, formatRelativeTime, getAccountHealthBadgeClass } from '../../utils/format';
import { cn } from '../../utils/cn';
import { useStore } from '../../store/useStore';

interface AccountListProps {
  account: TwitterAccount;
  onRefreshToken: (id: number) => void;
  onViewTweets: (account: TwitterAccount) => void;
  onNewTweet: (account: TwitterAccount) => void;
}

export const AccountList: React.FC<AccountListProps> = ({
  account,
  onRefreshToken,
  onViewTweets,
  onNewTweet,
}) => {
  const { selectedAccountIds, toggleAccountSelection } = useStore();
  const isSelected = selectedAccountIds.includes(account.id);

  return (
    <div className={cn(
      'flex items-center gap-4 p-4 bg-card border border-border rounded-lg hover:bg-accent/50 transition-colors',
      isSelected && 'ring-2 ring-primary'
    )}>
      {/* Selection checkbox */}
      <input
        type="checkbox"
        checked={isSelected}
        onChange={() => toggleAccountSelection(account.id)}
        className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
      />

      {/* Profile picture */}
      <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold">
        {account.displayName?.[0] || account.username[0]}
      </div>

      {/* Account info */}
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold">{account.displayName || account.username}</h3>
          <span className="text-muted-foreground">@{account.username}</span>
          {account.accountType === 'list_owner' && (
            <Badge variant="secondary" className="ml-2">List Owner</Badge>
          )}
        </div>
        
        <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
          <span>{formatNumber(account.followerCount || 0)} followers</span>
          <span>•</span>
          <span>{formatNumber(account.tweetCount || 0)} tweets</span>
          {account.lastActiveAt && (
            <>
              <span>•</span>
              <span>Active {formatRelativeTime(account.lastActiveAt)}</span>
            </>
          )}
        </div>
      </div>

      {/* Token status */}
      <Badge className={getAccountHealthBadgeClass(account.tokenStatus)}>
        {account.tokenStatus === 'healthy' && <CheckCircle size={12} className="mr-1" />}
        {account.tokenStatus === 'refresh_failed' && <AlertCircle size={12} className="mr-1" />}
        {account.tokenStatus?.replace('_', ' ') || 'Unknown'}
      </Badge>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={() => onNewTweet(account)}
        >
          <MessageSquare size={16} className="mr-2" />
          Tweet
        </Button>
        
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onViewTweets(account)}
        >
          View
        </Button>
        
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onRefreshToken(account.id)}
          disabled={account.tokenStatus === 'healthy'}
          title="Refresh token"
        >
          <RefreshCw size={16} />
        </Button>

        <button className="p-1 rounded-lg hover:bg-accent">
          <MoreVertical size={18} />
        </button>
      </div>
    </div>
  );
};