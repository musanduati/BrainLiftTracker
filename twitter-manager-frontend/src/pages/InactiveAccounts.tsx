import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, UserX, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { Card, CardContent } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { Skeleton } from '../components/common/Skeleton';
import { apiClient } from '../services/api';
import { TwitterAccount } from '../types';
import { getAvatarColor, getAvatarText } from '../utils/avatar';
import toast from 'react-hot-toast';

export const InactiveAccounts: React.FC = () => {
  const [inactiveAccounts, setInactiveAccounts] = useState<TwitterAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [accountsPerPage, setAccountsPerPage] = useState(40);

  useEffect(() => {
    loadInactiveAccounts();
  }, []);

  // Reset page when items per page changes
  useEffect(() => {
    setCurrentPage(1);
  }, [accountsPerPage]);

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


  // Pagination
  const totalPages = Math.ceil(inactiveAccounts.length / accountsPerPage);
  const paginatedAccounts = inactiveAccounts.slice(
    (currentPage - 1) * accountsPerPage,
    currentPage * accountsPerPage
  );

  if (loading) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 2xl:grid-cols-10 gap-3">
            {[...Array(20)].map((_, i) => (
              <Skeleton key={i} className="h-32" />
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
                Inactive Brainlifts
              </h1>
              <p className="text-muted-foreground mt-1">
                {inactiveAccounts.length} brainlift{inactiveAccounts.length !== 1 ? 's' : ''} without any content
                {totalPages > 1 && ` • Page ${currentPage} of ${totalPages}`}
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Show:</span>
                <select
                  value={accountsPerPage}
                  onChange={(e) => setAccountsPerPage(Number(e.target.value))}
                  className="px-3 py-1 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="20">20</option>
                  <option value="40">40</option>
                  <option value="60">60</option>
                  <option value="80">80</option>
                  <option value="100">100</option>
                  <option value="200">200</option>
                </select>
                <span className="text-sm text-muted-foreground">per page</span>
              </div>
              <Badge variant="secondary" className="text-orange-600">
                <AlertCircle size={14} className="mr-1" />
                Action Required
              </Badge>
            </div>
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
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 2xl:grid-cols-10 gap-3">
              {paginatedAccounts.map((account) => (
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
                          className="w-12 h-12 rounded-full object-cover ring-2 ring-orange-200"
                          onError={(e) => {
                            const target = e.target as HTMLImageElement;
                            target.style.display = 'none';
                            const fallback = target.nextElementSibling as HTMLElement;
                            if (fallback) fallback.style.display = 'flex';
                          }}
                        />
                      ) : null}
                      <div 
                        className={`w-12 h-12 rounded-full bg-gradient-to-br ${getAvatarColor(account.username)} flex items-center justify-center text-white font-bold text-sm ring-2 ring-orange-200 ${account.profilePicture ? 'hidden' : ''}`}
                        style={{ display: account.profilePicture ? 'none' : 'flex' }}
                      >
                        {getAvatarText(account.username, account.displayName)}
                      </div>
                    </div>
                    
                    {/* Account Info */}
                    <div className="text-center">
                      <h3 className="font-semibold text-xs break-words line-clamp-2" title={account.displayName || account.username}>
                        {account.displayName || account.username}
                      </h3>
                      <p className="text-muted-foreground text-[10px] break-all" title={`@${account.username}`}>
                        @{account.username}
                      </p>
                    </div>

                    {/* Token Status Indicator */}
                    <div className="flex justify-center">
                      <div className={`w-2 h-2 rounded-full ${getStatusColor(account.tokenStatus)}`} title={account.tokenStatus?.replace('_', ' ') || 'Unknown'} />
                    </div>

                    {/* Account Type */}
                    {account.accountType === 'list_owner' && (
                      <div className="flex justify-center">
                        <Badge variant="secondary" className="text-[10px] px-1 py-0">
                          List
                        </Badge>
                      </div>
                    )}

                  </div>
                </CardContent>
              </Card>
              </Link>
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