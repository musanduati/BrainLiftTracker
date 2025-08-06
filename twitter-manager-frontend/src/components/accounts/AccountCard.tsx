import React from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle, AlertCircle, Eye } from 'lucide-react';
import { TwitterAccount } from '../../types';
import { Card, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { formatNumber, formatRelativeTime, getAccountHealthBadgeClass } from '../../utils/format';
import { getAvatarColor, getAvatarText } from '../../utils/avatar';

interface AccountCardProps {
  account: TwitterAccount;
}

export const AccountCard: React.FC<AccountCardProps> = ({
  account,
}) => {

  return (
    <Card className="relative overflow-hidden transition-all duration-200 hover:shadow-lg">

      <CardContent className="p-6">
        <div className="flex flex-col items-center text-center">
          {/* Profile picture */}
          {account.profilePicture ? (
            <img
              src={account.profilePicture}
              alt={account.displayName || account.username}
              className="w-20 h-20 rounded-full mb-4 object-cover"
              onError={(e) => {
                // Fallback to colored avatar on error
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                const fallback = target.nextElementSibling as HTMLElement;
                if (fallback) fallback.style.display = 'flex';
              }}
            />
          ) : null}
          <div 
            className={`w-20 h-20 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-bold text-2xl mb-4 ${account.profilePicture ? 'hidden' : ''}`}
            style={{ display: account.profilePicture ? 'none' : 'flex' }}
          >
            {getAvatarText(account.username, account.displayName)}
          </div>

          {/* Account info */}
          <h3 className="font-semibold text-lg">{account.displayName || account.username}</h3>
          <p className="text-muted-foreground">@{account.username}</p>

          {/* Stats */}
          <div className="flex items-center gap-6 mt-4 text-sm">
            {account.tweetCount !== undefined && account.tweetCount > 0 && (
              <div className="text-center">
                <p className="font-semibold text-xl">{formatNumber(account.tweetCount)}</p>
                <p className="text-muted-foreground">Changes</p>
              </div>
            )}
            {account.threadCount !== undefined && account.threadCount > 0 && (
              <div className="text-center">
                <p className="font-semibold text-xl">{formatNumber(account.threadCount)}</p>
                <p className="text-muted-foreground">Threads</p>
              </div>
            )}
          </div>

          {/* Lists */}
          {account.listNames && account.listNames.length > 0 && (
            <div className="text-sm text-muted-foreground mt-3">
              {account.listNames.join(', ')}
            </div>
          )}

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
              {account.tokenStatus === 'healthy' ? 'Connected' : account.tokenStatus?.replace('_', ' ') || 'Unknown'}
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
                View Changes
              </Button>
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};