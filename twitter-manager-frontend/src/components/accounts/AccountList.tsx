import React from 'react';
import { Link } from 'react-router-dom';
import { TwitterAccount } from '../../types';
import { Card, CardContent } from '../common/Card';
import { formatNumber, formatRelativeTime } from '../../utils/format';
import { getAvatarColor, getAvatarText } from '../../utils/avatar';

interface AccountListProps {
  accounts: TwitterAccount[];
}

export const AccountList: React.FC<AccountListProps> = ({ accounts }) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 2xl:grid-cols-10 gap-3">
      {accounts.map((account) => (
        <Link key={account.id} to={`/accounts/${account.id}`}>
          <Card className="hover:shadow-md transition-all duration-200 cursor-pointer group h-full">
            <CardContent className="p-3">
              <div className="space-y-2">
                {/* Profile Picture */}
                <div className="flex justify-center">
                  {account.profilePicture ? (
                    <img 
                      src={account.profilePicture}
                      alt={account.displayName || account.username}
                      className="w-12 h-12 rounded-full object-cover ring-2 ring-primary/20"
                      onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        target.style.display = 'none';
                        const fallback = target.nextElementSibling as HTMLElement;
                        if (fallback) fallback.style.display = 'flex';
                      }}
                    />
                  ) : null}
                  <div 
                    className={`w-12 h-12 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-bold text-sm ring-2 ring-primary/20 ${account.profilePicture ? 'hidden' : ''}`}
                    style={{ display: account.profilePicture ? 'none' : 'flex' }}
                  >
                    {getAvatarText(account.username, account.displayName)}
                  </div>
                </div>
                
                {/* Account Info - Min height for consistency, allow wrapping */}
                <div className="text-center min-h-[2.75rem] flex flex-col justify-center">
                  <h3 className="font-semibold text-xs break-words line-clamp-2 px-1" title={account.displayName || account.username}>
                    {account.displayName || account.username}
                  </h3>
                  <p className="text-muted-foreground text-[10px] truncate" title={`@${account.username}`}>
                    @{account.username}
                  </p>
                </div>

                {/* Stats */}
                <div className="space-y-1">
                  {account.followerCount !== undefined && (
                    <div className="flex items-center justify-center text-[10px]">
                      <span className="font-semibold">{formatNumber(account.followerCount)}</span>
                      <span className="text-muted-foreground ml-1">followers</span>
                    </div>
                  )}
                  
                  {/* Active Status */}
                  {account.lastActiveAt && (
                    <div className="flex items-center justify-center">
                      <span className="text-[10px] text-muted-foreground truncate">
                        Active {formatRelativeTime(account.lastActiveAt)}
                      </span>
                    </div>
                  )}
                </div>


              </div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
};