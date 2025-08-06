import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, UserX, AlertCircle, Calendar, Clock, ChevronLeft, ChevronRight } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent, CardHeader } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import { TwitterAccount } from '../types';
import { getAvatarColor, getAvatarText } from '../utils/avatar';
import { formatRelativeTime } from '../utils/format';
import toast from 'react-hot-toast';

const ACCOUNTS_PER_PAGE = 15;

export const InactiveAccounts: React.FC = () => {
  const [inactiveAccounts, setInactiveAccounts] = useState<TwitterAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    loadInactiveAccounts();
  }, []);

  const loadInactiveAccounts = async () => {
    try {
      setLoading(true);
      const [accountsData, tweetsData, threadsData] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getTweets(),
        apiClient.getThreads()
      ]);

      // Filter accounts without tweets or threads (inactive)
      const accountsWithoutContent = accountsData.filter(account => {
        const hasTweets = tweetsData.some((tweet: any) => tweet.username === account.username);
        const hasThreads = threadsData.some((thread: any) => thread.account_username === account.username);
        return !hasTweets && !hasThreads;
      });

      setInactiveAccounts(accountsWithoutContent);
    } catch (error) {
      toast.error('Failed to load inactive accounts');
      console.error('Inactive accounts error:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (tokenStatus?: string) => {
    switch (tokenStatus) {
      case 'healthy':
        return 'text-green-500';
      case 'expired':
        return 'text-yellow-500';
      case 'refresh_failed':
        return 'text-red-500';
      default:
        return 'text-gray-500';
    }
  };

  const getTimeInactive = (lastActiveAt?: string) => {
    if (!lastActiveAt) return 'Never active';
    return `Last active ${formatRelativeTime(lastActiveAt)}`;
  };

  // Pagination
  const totalPages = Math.ceil(inactiveAccounts.length / ACCOUNTS_PER_PAGE);
  const paginatedAccounts = inactiveAccounts.slice(
    (currentPage - 1) * ACCOUNTS_PER_PAGE,
    currentPage * ACCOUNTS_PER_PAGE
  );

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {[...Array(10)].map((_, i) => (
              <Skeleton key={i} className="h-48" />
            ))}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <TopBar />
      
      <div className="p-6">
        {/* Back Button */}
        <Link to="/" className="inline-flex mb-6">
          <Button variant="ghost" size="sm">
            <ArrowLeft size={16} className="mr-2" />
            Back to Dashboard
          </Button>
        </Link>

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold flex items-center gap-3">
                <UserX size={28} className="text-orange-500" />
                Inactive Accounts
              </h1>
              <p className="text-muted-foreground mt-1">
                {inactiveAccounts.length} account{inactiveAccounts.length !== 1 ? 's' : ''} without any content
                {totalPages > 1 && ` • Page ${currentPage} of ${totalPages}`}
              </p>
            </div>
            <Badge variant="secondary" className="text-orange-600">
              <AlertCircle size={14} className="mr-1" />
              Action Required
            </Badge>
          </div>
        </div>

        {/* Accounts Grid */}
        {inactiveAccounts.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <UserX size={48} className="mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No Inactive Accounts</h3>
              <p className="text-muted-foreground">
                All accounts have posted content. Great job!
              </p>
              <Link to="/accounts" className="inline-block mt-4">
                <Button>View All Accounts</Button>
              </Link>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
              {paginatedAccounts.map((account) => (
              <Card key={account.id} className="hover:shadow-lg transition-all duration-200">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-bold text-lg`}>
                      {getAvatarText(account.username, account.displayName)}
                    </div>
                    <Badge variant="outline" className="text-orange-600 text-xs">
                      No Content
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="space-y-3">
                    {/* Account Info */}
                    <div>
                      <h3 className="font-semibold text-sm truncate" title={account.displayName || account.username}>
                        {account.displayName || account.username}
                      </h3>
                      <p className="text-muted-foreground text-xs truncate" title={`@${account.username}`}>
                        @{account.username}
                      </p>
                    </div>

                    {/* Status Info - more compact */}
                    <div className="space-y-1 text-xs">
                      <div className="flex items-center gap-1">
                        <Clock size={12} className="text-muted-foreground" />
                        <span className="text-muted-foreground truncate">{getTimeInactive(account.lastActiveAt)}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Calendar size={12} className="text-muted-foreground" />
                        <span className="text-muted-foreground truncate">
                          Added {new Date(account.createdAt).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className={`w-2 h-2 rounded-full ${getStatusColor(account.tokenStatus)}`} />
                        <span className="text-muted-foreground truncate">
                          {account.tokenStatus?.replace('_', ' ') || 'Unknown'}
                        </span>
                      </div>
                    </div>

                    {/* Account Type */}
                    {account.accountType === 'list_owner' && (
                      <Badge variant="secondary" className="w-fit text-xs">
                        List Owner
                      </Badge>
                    )}

                  </div>
                </CardContent>
              </Card>
            ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft size={16} />
                </Button>
                
                <div className="flex items-center gap-1">
                  {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => {
                    // Show first page, last page, current page, and pages around current
                    if (
                      page === 1 ||
                      page === totalPages ||
                      (page >= currentPage - 1 && page <= currentPage + 1)
                    ) {
                      return (
                        <Button
                          key={page}
                          variant={page === currentPage ? 'primary' : 'ghost'}
                          size="sm"
                          onClick={() => setCurrentPage(page)}
                          className="w-8 h-8 p-0"
                        >
                          {page}
                        </Button>
                      );
                    } else if (
                      page === currentPage - 2 ||
                      page === currentPage + 2
                    ) {
                      return <span key={page} className="px-1">...</span>;
                    }
                    return null;
                  })}
                </div>
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                >
                  <ChevronRight size={16} />
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
};