import React, { useEffect, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
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
    isLoadingAccounts,
    setAccounts,
    setLoadingAccounts,
    setLists,
  } = useStore();

  const [selectedListId, setSelectedListId] = useState<string | null>(null);
  const [accountsByList, setAccountsByList] = useState<{
    lists: any[];
    unassigned_accounts: TwitterAccount[];
  }>({ lists: [], unassigned_accounts: [] });
  const [filteredAccounts, setFilteredAccounts] = useState<TwitterAccount[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [sortBy, setSortBy] = useState<'followers-desc' | 'followers-asc' | 'username' | 'displayName' | 'lastActive' | 'posts' | 'activity' | 'onboarded-newest' | 'onboarded-oldest'>('followers-desc');
  const [accountsPerPage, setAccountsPerPage] = useState(40);

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

  // Reset page when filter, sort, or items per page changes
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedListId, sortBy, accountsPerPage]);

  // Sorting function
  const sortAccounts = (accounts: TwitterAccount[]) => {
    const sorted = [...accounts];
    
    switch (sortBy) {
      case 'followers-desc':
        sorted.sort((a, b) => (b.followerCount || 0) - (a.followerCount || 0));
        break;
      case 'followers-asc':
        sorted.sort((a, b) => (a.followerCount || 0) - (b.followerCount || 0));
        break;
      case 'username':
        sorted.sort((a, b) => a.username.localeCompare(b.username));
        break;
      case 'displayName':
        sorted.sort((a, b) => (a.displayName || a.username).localeCompare(b.displayName || b.username));
        break;
      case 'lastActive':
        sorted.sort((a, b) => {
          const dateA = a.lastActiveAt ? new Date(a.lastActiveAt).getTime() : 0;
          const dateB = b.lastActiveAt ? new Date(b.lastActiveAt).getTime() : 0;
          return dateB - dateA;
        });
        break;
      case 'posts':
        sorted.sort((a, b) => {
          const postsA = a.postCount || ((a.tweetCount || 0) + (a.threadCount || 0));
          const postsB = b.postCount || ((b.tweetCount || 0) + (b.threadCount || 0));
          return postsB - postsA;
        });
        break;
      case 'activity':
        sorted.sort((a, b) => {
          const totalA = a.postCount || ((a.tweetCount || 0) + (a.threadCount || 0));
          const totalB = b.postCount || ((b.tweetCount || 0) + (b.threadCount || 0));
          return totalB - totalA;
        });
        break;
      case 'onboarded-newest':
        sorted.sort((a, b) => {
          const dateA = a.createdAt ? new Date(a.createdAt).getTime() : 0;
          const dateB = b.createdAt ? new Date(b.createdAt).getTime() : 0;
          return dateB - dateA; // Newest first
        });
        break;
      case 'onboarded-oldest':
        sorted.sort((a, b) => {
          const dateA = a.createdAt ? new Date(a.createdAt).getTime() : 0;
          const dateB = b.createdAt ? new Date(b.createdAt).getTime() : 0;
          return dateA - dateB; // Oldest first
        });
        break;
    }
    
    return sorted;
  };

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
            if (fullAccount) {
              // Use full account data with all fields
              allAccounts.push({
                ...fullAccount,
                listNames: getAccountListNames(member.id)
              });
            } else {
              // Fallback to member data
              allAccounts.push({
                ...member,
                tweetCount: 0,
                threadCount: 0,
                followerCount: member.followerCount || 0,
                listNames: getAccountListNames(member.id)
              });
            }
          }
        });
      });
      
      // Add unassigned accounts
      accountsByList.unassigned_accounts?.forEach((unassigned: any) => {
        if (!allAccounts.find(a => a.id === unassigned.id)) {
          const fullAccount = accounts.find(a => a.id === unassigned.id);
          if (fullAccount) {
            // Use full account data with all fields
            allAccounts.push({
              ...fullAccount,
              listNames: []
            });
          } else {
            // Fallback to unassigned data
            allAccounts.push({
              ...unassigned,
              tweetCount: 0,
              threadCount: 0,
              followerCount: unassigned.followerCount || 0,
              listNames: []
            });
          }
        }
      });
      
      // Apply sorting
      const sortedAccounts = sortAccounts(allAccounts);
      setFilteredAccounts(sortedAccounts);
    } else if (selectedListId === 'unassigned') {
      // Show unassigned accounts - need to merge with full account data
      const unassignedWithFullData = accountsByList.unassigned_accounts.map((unassigned: any) => {
        const fullAccount = accounts.find(a => a.id === unassigned.id);
        return fullAccount ? { ...fullAccount, listNames: [] } : { ...unassigned, listNames: [] };
      });
      
      // Apply sorting
      const sortedAccounts = sortAccounts(unassignedWithFullData);
      setFilteredAccounts(sortedAccounts);
    } else {
      // Show accounts from selected list - merge with full account data
      const list = accountsByList.lists.find(l => l.id === selectedListId);
      const accountsWithLists = (list?.members || []).map((member: any) => {
        const fullAccount = accounts.find(a => a.id === member.id);
        if (fullAccount) {
          return { ...fullAccount, listNames: [list.name] };
        } else {
          return { 
            ...member, 
            tweetCount: 0,
            threadCount: 0,
            followerCount: member.followerCount || 0,
            listNames: [list.name] 
          };
        }
      });
      
      // Apply sorting
      const sortedAccounts = sortAccounts(accountsWithLists);
      setFilteredAccounts(sortedAccounts);
    }
  }, [selectedListId, accounts, accountsByList, sortBy]);

  // Calculate paginated accounts
  const paginatedAccounts = useMemo(() => {
    const startIndex = (currentPage - 1) * accountsPerPage;
    const endIndex = startIndex + accountsPerPage;
    return filteredAccounts.slice(startIndex, endIndex);
  }, [filteredAccounts, currentPage, accountsPerPage]);

  // Calculate total pages
  const totalPages = Math.ceil(filteredAccounts.length / accountsPerPage);

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
            threadCount: accountThreadCount,
            followerCount: account.followerCount || 0
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

        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl font-semibold">
            Brainlifts ({filteredAccounts.length})
          </h2>
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

        {/* Sort and Display Controls */}
        <div className="mb-4 flex justify-between items-center">
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
          
          <div className="flex items-center gap-2">
            <ArrowUpDown size={16} className="text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
              className="px-3 py-1 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="followers-desc">Most Followers</option>
              <option value="followers-asc">Least Followers</option>
              <option value="username">Username (A-Z)</option>
              <option value="displayName">Display Name (A-Z)</option>
              <option value="onboarded-newest">Newest Onboarded</option>
              <option value="onboarded-oldest">Oldest Onboarded</option>
              <option value="lastActive">Most Recently Active</option>
              <option value="activity">Total Activity</option>
              <option value="posts">Most Posts</option>
            </select>
          </div>
        </div>

        {/* Account Grid */}
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
            <AccountList accounts={paginatedAccounts} />
            
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