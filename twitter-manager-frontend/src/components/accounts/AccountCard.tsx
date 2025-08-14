import React from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Calendar } from 'lucide-react';
import { TwitterAccount } from '../../types';
import { Card, CardContent } from '../common/Card';
import { Badge } from '../common/Badge';
import { formatNumber } from '../../utils/format';
import { getAvatarColor, getAvatarText } from '../../utils/avatar';
import { format } from 'date-fns';

interface AccountCardProps {
  account: TwitterAccount;
}

export const AccountCard: React.FC<AccountCardProps> = ({
  account,
}) => {
  const navigate = useNavigate();

  return (
    <div 
      className="cursor-pointer transition-transform hover:scale-[1.02] h-full"
      onClick={() => navigate(`/accounts/${account.id}`)}
      title={`View ${account.displayName || account.username}'s tweets`}
    >
      <Card className="relative overflow-hidden transition-all duration-200 hover:shadow-xl h-full flex flex-col">
        <CardContent className="p-4 flex-1 flex flex-col">
        <div className="flex flex-col items-center text-center flex-1">
          {/* Profile picture - smaller */}
          {account.profilePicture ? (
            <img
              src={account.profilePicture}
              alt={account.displayName || account.username}
              className="w-16 h-16 rounded-full mb-3 object-cover"
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
            className={`w-16 h-16 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-bold text-xl mb-3 ${account.profilePicture ? 'hidden' : ''}`}
            style={{ display: account.profilePicture ? 'none' : 'flex' }}
          >
            {getAvatarText(account.username, account.displayName)}
          </div>

          {/* Account info - Min height for consistency, allow wrapping */}
          <div className="min-h-[2.5rem] flex flex-col justify-center">
            <h3 className="font-semibold text-sm break-words line-clamp-2 px-1" title={account.displayName || account.username}>
              {account.displayName || account.username}
            </h3>
            <p className="text-muted-foreground text-xs truncate w-full" title={`@${account.username}`}>
              @{account.username}
            </p>
          </div>

          {/* Stats - show tweets, threads, and followers */}
          <div className="flex items-center gap-3 mt-3 text-xs">
            <div className="text-center">
              <p className="font-semibold text-base">{formatNumber(account.tweetCount || 0)}</p>
              <p className="text-muted-foreground text-xs">Tweets</p>
            </div>
            <div className="text-center">
              <p className="font-semibold text-base">{formatNumber(account.threadCount || 0)}</p>
              <p className="text-muted-foreground text-xs">Threads</p>
            </div>
            <div className="text-center">
              <p className="font-semibold text-base">{formatNumber(account.followerCount || 0)}</p>
              <p className="text-muted-foreground text-xs">Followers</p>
            </div>
          </div>

          {/* Onboarding date */}
          <div className="flex items-center gap-1 mt-2 text-xs text-muted-foreground">
            <Calendar size={12} />
            <span>Onboarded {format(new Date(account.createdAt), 'MMM d, yyyy')}</span>
          </div>

          {/* Lists - smaller */}
          {account.listNames && account.listNames.length > 0 && (
            <div className="text-xs text-muted-foreground mt-2 truncate w-full px-1" title={account.listNames.join(', ')}>
              {account.listNames.join(', ')}
            </div>
          )}

          {/* Status badges - smaller */}
          <div className="flex flex-wrap gap-1 mt-3 justify-center min-h-[24px]">
            {/* Account type */}
            {account.accountType === 'list_owner' && (
              <Badge variant="secondary" className="text-xs py-0 px-1">List Owner</Badge>
            )}

            {/* Token status - simplified */}
            {account.tokenStatus === 'refresh_failed' && (
              <Badge className="bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400 text-xs py-0 px-1">
                <AlertCircle size={10} className="mr-1" />
                Failed
              </Badge>
            )}
          </div>

        </div>
      </CardContent>
    </Card>
    </div>
  );
};