import React from 'react';
import { Link } from 'react-router-dom';
import { Eye, CheckCircle, AlertCircle } from 'lucide-react';
import { TwitterAccount } from '../../types';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { formatNumber, formatRelativeTime, getAccountHealthBadgeClass } from '../../utils/format';
import { getAvatarColor, getAvatarText } from '../../utils/avatar';

interface AccountListProps {
  accounts: TwitterAccount[];
}

export const AccountList: React.FC<AccountListProps> = ({ accounts }) => {
  return (
    <div className="space-y-2">
      {accounts.map((account) => (
        <div
          key={account.id}
          className="flex items-center gap-4 p-4 bg-card border border-border rounded-lg hover:bg-accent/50 transition-colors"
        >
          {/* Profile picture */}
          <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-bold`}>
            {getAvatarText(account.username, account.displayName)}
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
              {account.tweetCount !== undefined && account.tweetCount > 0 && (
                <>
                  <span>{formatNumber(account.tweetCount)} tweets</span>
                  {(account.threadCount !== undefined && account.threadCount > 0) && <span>•</span>}
                </>
              )}
              {account.threadCount !== undefined && account.threadCount > 0 && (
                <span>{formatNumber(account.threadCount)} threads</span>
              )}
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
            {account.tokenStatus === 'healthy' ? 'Connected' : account.tokenStatus?.replace('_', ' ') || 'Unknown'}
          </Badge>

          {/* Actions */}
          <Link to={`/accounts/${account.id}`}>
            <Button
              variant="primary"
              size="sm"
            >
              <Eye size={16} className="mr-2" />
              View Profile
            </Button>
          </Link>
        </div>
      ))}
    </div>
  );
};