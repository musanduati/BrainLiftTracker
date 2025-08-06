import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { Grid3x3, List, RefreshCw, ArrowLeft, UserCheck, ChevronLeft, ChevronRight } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { AccountCard } from '../components/accounts/AccountCard';
import { AccountList } from '../components/accounts/AccountList';
import { ListFilter } from '../components/accounts/ListFilter';
import { Button } from '../components/common/Button';
import { Skeleton } from '../components/common/Skeleton';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import toast from 'react-hot-toast';
import { TwitterAccount } from '../types';

export const Accounts: React.FC = () => {
  const {
    accounts,
    accountViewMode,
    isLoadingAccounts,
    setAccounts,
    setAccountViewMode,
    setLoadingAccounts,
    setLists,
  } = useStore();

  const [selectedListId, setSelectedListId] = useState<string | null>(null);
  const [accountsByList, setAccountsByList] = useState<{
    lists: any[];
    unassigned_accounts: TwitterAccount[];
  }>({ lists: [], unassigned_accounts: [] });
  const [filteredAccounts, setFilteredAccounts] = useState<TwitterAccount[]>([]);
  const [isSyncingProfiles, setIsSyncingProfiles] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const accountsPerPage = 15;

  useEffect(() => {
    loadAccounts();
  }, []);

  // Helper function to get list names for an account
  const getAccountListNames = (accountId: number): string[] => {
    const listNames: string[] = [];
    accountsByList.lists.forEach(list => {
      if (list.members?.some((member: any) => member.id === accountId)) {
        listNames.push(list.name);
      }
    });
    return listNames;
  };

  // Reset page when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedListId]);

  useEffect(() => {
    // Filter accounts based on selected list
    if (selectedListId === null) {
      // Show ALL accounts from accountsByList when "All" is selected
      const allAccounts: TwitterAccount[] = [];
      
      // Add all accounts from lists
      accountsByList.lists.forEach(list => {
        list.members?.forEach((member: any) => {
          // Check if we already have this account
          if (!allAccounts.find(a => a.id === member.id)) {
            // Find the full account data if available
            const fullAccount = accounts.find(a => a.id === member.id);
            allAccounts.push({
              ...member,
              tweetCount: fullAccount?.tweetCount || 0,
              threadCount: fullAccount?.threadCount || 0,
              listNames: getAccountListNames(member.id)
            });
          }
        });
      });
      
      // Add unassigned accounts
      accountsByList.unassigned_accounts?.forEach((unassigned: any) => {
        if (!allAccounts.find(a => a.id === unassigned.id)) {
          const fullAccount = accounts.find(a => a.id === unassigned.id);
          allAccounts.push({
            ...unassigned,
            tweetCount: fullAccount?.tweetCount || 0,
            threadCount: fullAccount?.threadCount || 0,
            listNames: []
          });
        }
      });
      
      // Sort accounts by total activity (tweets + threads) in descending order
      allAccounts.sort((a, b) => {
        const totalA = (a.tweetCount || 0) + (a.threadCount || 0);
        const totalB = (b.tweetCount || 0) + (b.threadCount || 0);
        return totalB - totalA;
      });
      
      setFilteredAccounts(allAccounts);
    } else if (selectedListId === 'unassigned') {
      // Show unassigned accounts - need to merge with full account data
      const unassignedWithFullData = accountsByList.unassigned_accounts.map((unassigned: any) => {
        const fullAccount = accounts.find(a => a.id === unassigned.id);
        return fullAccount ? { ...fullAccount, listNames: [] } : { ...unassigned, listNames: [] };
      });
      
      // Sort by activity
      unassignedWithFullData.sort((a, b) => {
        const totalA = (a.tweetCount || 0) + (a.threadCount || 0);
        const totalB = (b.tweetCount || 0) + (b.threadCount || 0);
        return totalB - totalA;
      });
      
      setFilteredAccounts(unassignedWithFullData);
    } else {
      // Show accounts from selected list - merge with full account data
      const list = accountsByList.lists.find(l => l.id === selectedListId);
      const accountsWithLists = (list?.members || []).map((member: any) => {
        const fullAccount = accounts.find(a => a.id === member.id);
        return fullAccount ? { ...fullAccount, listNames: [list.name] } : { ...member, listNames: [list.name] };
      });
      
      // Sort by activity
      accountsWithLists.sort((a: any, b: any) => {
        const totalA = (a.tweetCount || 0) + (a.threadCount || 0);
        const totalB = (b.tweetCount || 0) + (b.threadCount || 0);
        return totalB - totalA;
      });
      
      setFilteredAccounts(accountsWithLists);
    }
  }, [selectedListId, accounts, accountsByList]);

  // Calculate paginated accounts
  const paginatedAccounts = useMemo(() => {
    const startIndex = (currentPage - 1) * accountsPerPage;
    const endIndex = startIndex + accountsPerPage;
    return filteredAccounts.slice(startIndex, endIndex);
  }, [filteredAccounts, currentPage]);

  // Calculate total pages
  const totalPages = Math.ceil(filteredAccounts.length / accountsPerPage);

  const handleSyncProfiles = async () => {
    try {
      setIsSyncingProfiles(true);
      const result = await apiClient.syncAccountProfiles();
      
      if (result.results.synced.length > 0) {
        toast.success(`Successfully synced ${result.results.synced.length} account profiles`);
        // Reload accounts to show updated profiles
        await loadAccounts();
      }
      
      if (result.results.failed.length > 0) {
        toast.error(`Failed to sync ${result.results.failed.length} accounts`);
        console.error('Sync failures:', result.results.failed);
      }
    } catch (error) {
      toast.error('Failed to sync account profiles');
      console.error('Sync profiles error:', error);
    } finally {
      setIsSyncingProfiles(false);
    }
  };

  const loadAccounts = async () => {
    try {
      setLoadingAccounts(true);
      const [accountsData, tweetsData, threadsData, listsData, accountsByListData] = await Promise.all([
        apiClient.getAccounts(),
        apiClient.getTweets(),
        apiClient.getThreads(),
        apiClient.getLists(),
        apiClient.getAccountsByLists()
      ]);
      
      // Store lists data
      setLists(listsData);
      setAccountsByList(accountsByListData);
      
      // Filter accounts to show those with either tweets or threads
      const accountsWithContent = accountsData
        .filter(account => {
          const hasTweets = tweetsData.some((tweet: any) => tweet.username === account.username);
          const hasThreads = threadsData.some((thread: any) => thread.account_username === account.username);
          return hasTweets || hasThreads;
        })
        .map(account => {
          // Count tweets for this account
          const accountTweetCount = tweetsData.filter(
            (tweet: any) => tweet.username === account.username
          ).length;
          
          // Count threads for this account
          const accountThreadCount = threadsData.filter(
            (thread: any) => thread.account_username === account.username
          ).length;
          
          return {
            ...account,
            tweetCount: accountTweetCount,
            threadCount: accountThreadCount
          };
        });
      
      setAccounts(accountsWithContent);
    } catch (error) {
      toast.error('Failed to load accounts');
      console.error('Load accounts error:', error);
    } finally {
      setLoadingAccounts(false);
    }
  };

  // Calculate account counts for each list
  const getAccountCounts = () => {
    const counts: Record<string, number> = {};
    
    accountsByList.lists.forEach(list => {
      counts[list.id] = list.member_count || 0;
    });
    
    counts.unassigned = accountsByList.unassigned_accounts?.length || 0;
    
    return counts;
  };

  if (isLoadingAccounts) {
    return (
      <>
        <TopBar />
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
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

        {/* Header Actions */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-semibold">
              Twitter Accounts ({filteredAccounts.length})
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              Sorted by activity (most active first)
            </p>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setAccountViewMode(accountViewMode === 'grid' ? 'list' : 'grid')}
              title={accountViewMode === 'grid' ? 'Switch to list view' : 'Switch to grid view'}
            >
              {accountViewMode === 'grid' ? <List size={20} /> : <Grid3x3 size={20} />}
            </Button>
            
            <Button
              variant="secondary"
              size="sm"
              onClick={handleSyncProfiles}
              disabled={isSyncingProfiles || isLoadingAccounts}
              title="Sync profile pictures and names from Twitter"
            >
              <UserCheck size={16} className={`mr-2 ${isSyncingProfiles ? 'animate-spin' : ''}`} />
              Sync Profiles
            </Button>
            
            <Button
              variant="secondary"
              size="sm"
              onClick={loadAccounts}
              disabled={isLoadingAccounts}
            >
              <RefreshCw size={16} className={`mr-2 ${isLoadingAccounts ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* List Filter */}
        <div className="mb-6">
          <ListFilter
            lists={accountsByList.lists}
            selectedListId={selectedListId}
            onSelectList={setSelectedListId}
            accountCounts={getAccountCounts()}
          />
        </div>

        {/* Account Grid/List */}
        {filteredAccounts.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground">
              {selectedListId === 'unassigned' 
                ? 'No unassigned accounts found' 
                : selectedListId 
                  ? 'No accounts in this list' 
                  : 'No accounts found'}
            </p>
          </div>
        ) : (
          <>
            {accountViewMode === 'grid' ? (
              <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                {paginatedAccounts.map((account) => (
                  <AccountCard
                    key={account.id}
                    account={account}
                  />
                ))}
              </div>
            ) : (
              <AccountList accounts={paginatedAccounts} />
            )}
            
            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-6 py-4 border-t">
                <div className="text-sm text-muted-foreground">
                  Showing {(currentPage - 1) * accountsPerPage + 1} to{' '}
                  {Math.min(currentPage * accountsPerPage, filteredAccounts.length)} of{' '}
                  {filteredAccounts.length} accounts
                </div>
                
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft size={16} className="mr-1" />
                    Previous
                  </Button>
                  
                  <div className="flex items-center gap-1">
                    {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                      let pageNum;
                      if (totalPages <= 5) {
                        pageNum = i + 1;
                      } else if (currentPage <= 3) {
                        pageNum = i + 1;
                      } else if (currentPage >= totalPages - 2) {
                        pageNum = totalPages - 4 + i;
                      } else {
                        pageNum = currentPage - 2 + i;
                      }
                      
                      return (
                        <Button
                          key={pageNum}
                          variant={pageNum === currentPage ? 'primary' : 'ghost'}
                          size="sm"
                          onClick={() => setCurrentPage(pageNum)}
                          className="w-8 h-8 p-0"
                        >
                          {pageNum}
                        </Button>
                      );
                    })}
                  </div>
                  
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                  >
                    Next
                    <ChevronRight size={16} className="ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
};