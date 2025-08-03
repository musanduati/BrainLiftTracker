import React from 'react';
import { Link } from 'react-router-dom';
import { MoreVertical, RefreshCw, CheckCircle, AlertCircle, Eye } from 'lucide-react';
import { TwitterAccount } from '../../types';
import { Card, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { formatNumber, formatRelativeTime, getAccountHealthBadgeClass } from '../../utils/format';
import { cn } from '../../utils/cn';
import { useStore } from '../../store/useStore';

interface AccountCardProps {
  account: TwitterAccount;
  onRefreshToken: (id: number) => void;
  onViewTweets: (account: TwitterAccount) => void;
  onNewTweet: (account: TwitterAccount) => void;
}

export const AccountCard: React.FC<AccountCardProps> = ({
  account,
  onRefreshToken,
  onViewTweets,
  onNewTweet,
}) => {
  const { selectedAccountIds, toggleAccountSelection } = useStore();
  const isSelected = selectedAccountIds.includes(account.id);

  return (
    <Card className={cn(
      'relative overflow-hidden transition-all duration-200 hover:shadow-lg',
      isSelected && 'ring-2 ring-primary'
    )}>
      {/* Selection checkbox */}
      <div className="absolute top-4 left-4">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => toggleAccountSelection(account.id)}
          className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
        />
      </div>

      {/* More options */}
      <button className="absolute top-4 right-4 p-1 rounded-lg hover:bg-accent">
        <MoreVertical size={18} />
      </button>

      <CardContent className="pt-8">
        <div className="flex flex-col items-center text-center">
          {/* Profile picture */}
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white font-bold text-2xl mb-4">
            {account.displayName?.[0] || account.username[0]}
          </div>

          {/* Account info */}
          <h3 className="font-semibold text-lg">{account.displayName || account.username}</h3>
          <p className="text-muted-foreground">@{account.username}</p>

          {/* Stats */}
          <div className="flex items-center gap-4 mt-4 text-sm">
            <div>
              <p className="font-semibold">{formatNumber(account.followerCount || 0)}</p>
              <p className="text-muted-foreground">Followers</p>
            </div>
            <div className="border-l border-border pl-4">
              <p className="font-semibold">{formatNumber(account.tweetCount || 0)}</p>
              <p className="text-muted-foreground">Tweets</p>
            </div>
          </div>

          {/* Status badges */}
          <div className="flex flex-wrap gap-2 mt-4">
            {/* Account type */}
            {account.accountType === 'list_owner' && (
              <Badge variant="secondary">List Owner</Badge>
            )}

            {/* Token status */}
            <Badge className={getAccountHealthBadgeClass(account.tokenStatus)}>
              {account.tokenStatus === 'healthy' && <CheckCircle size={12} className="mr-1" />}
              {account.tokenStatus === 'refresh_failed' && <AlertCircle size={12} className="mr-1" />}
              {account.tokenStatus?.replace('_', ' ') || 'Unknown'}
            </Badge>
          </div>

          {/* Last active */}
          {account.lastActiveAt && (
            <p className="text-xs text-muted-foreground mt-2">
              Active {formatRelativeTime(account.lastActiveAt)}
            </p>
          )}

          {/* Actions */}
          <div className="flex flex-col gap-2 w-full mt-6">
            <Link to={`/accounts/${account.id}`} className="w-full">
              <Button
                variant="primary"
                size="sm"
                className="w-full"
              >
                <Eye size={16} className="mr-2" />
                View Profile & Tweets
              </Button>
            </Link>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onRefreshToken(account.id);
              }}
              disabled={account.tokenStatus === 'healthy'}
              title="Refresh token"
              className="w-full"
            >
              <RefreshCw size={16} className="mr-2" />
              Refresh Token
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};