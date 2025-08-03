import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Grid3x3, List, Plus, RefreshCw, CheckSquare, Square, Users, MessageSquare } from 'lucide-react';
import { TopBar } from '../components/layout/TopBar';
import { AccountCard } from '../components/accounts/AccountCard';
import { AccountList } from '../components/accounts/AccountList';
import { Button } from '../components/common/Button';
import { ComposeTweetModal } from '../components/tweets/ComposeTweetModal';
import { Skeleton } from '../components/common/Skeleton';
import { useStore } from '../store/useStore';
import { apiClient } from '../services/api';
import { TwitterAccount } from '../types';
import toast from 'react-hot-toast';

export const Accounts: React.FC = () => {
  const navigate = useNavigate();
  const {
    accounts,
    accountViewMode,
    selectedAccountIds,
    isLoadingAccounts,
    setAccounts,
    setAccountViewMode,
    setLoadingAccounts,
    openComposeTweetModal,
    closeComposeTweetModal,
    isComposeTweetModalOpen,
    selectAllAccounts,
    clearAccountSelection,
  } = useStore();

  const [isRefreshingTokens, setIsRefreshingTokens] = useState(false);
  const [selectedAccountForTweet, setSelectedAccountForTweet] = useState<TwitterAccount | null>(null);

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setLoadingAccounts(true);
      const data = await apiClient.getAccounts();
      setAccounts(data);
    } catch (error) {
      toast.error('Failed to load accounts');
      console.error('Load accounts error:', error);
    } finally {
      setLoadingAccounts(false);
    }
  };

  const handleRefreshToken = async (accountId: number) => {
    try {
      const updatedAccount = await apiClient.refreshToken(accountId);
      useStore.getState().updateAccount(accountId, updatedAccount);
      toast.success('Token refreshed successfully');
    } catch (error) {
      toast.error('Failed to refresh token');
      console.error('Refresh token error:', error);
    }
  };

  const handleRefreshAllTokens = async () => {
    try {
      setIsRefreshingTokens(true);
      const result = await apiClient.refreshAllTokens();
      toast.success(`Refreshed ${result.refreshed} tokens`);
      if (result.failed > 0) {
        toast.error(`Failed to refresh ${result.failed} tokens`);
      }
      await loadAccounts(); // Reload to get updated status
    } catch (error) {
      toast.error('Failed to refresh tokens');
      console.error('Refresh all tokens error:', error);
    } finally {
      setIsRefreshingTokens(false);
    }
  };

  const handleViewTweets = (account: TwitterAccount) => {
    navigate(`/tweets?accountId=${account.id}`);
  };

  const handleNewTweet = (account: TwitterAccount) => {
    setSelectedAccountForTweet(account);
    openComposeTweetModal();
  };

  const handleBatchTweet = () => {
    if (selectedAccountIds.length === 0) {
      toast.error('Please select at least one account');
      return;
    }
    openComposeTweetModal();
  };

  const handleComposeTweet = async (content: string, accountIds: number[]) => {
    try {
      const promises = accountIds.map(accountId =>
        apiClient.createTweet(accountId, content)
      );
      
      const results = await Promise.allSettled(promises);
      const successful = results.filter(r => r.status === 'fulfilled').length;
      const failed = results.filter(r => r.status === 'rejected').length;

      if (successful > 0) {
        toast.success(`Created ${successful} tweet${successful > 1 ? 's' : ''}`);
      }
      if (failed > 0) {
        toast.error(`Failed to create ${failed} tweet${failed > 1 ? 's' : ''}`);
      }
    } catch (error) {
      toast.error('Failed to create tweets');
      console.error('Create tweets error:', error);
    }
  };

  const handleAddAccount = async () => {
    try {
      const authUrl = await apiClient.getAuthUrl();
      window.location.href = authUrl;
    } catch (error) {
      toast.error('Failed to get authorization URL');
      console.error('Get auth URL error:', error);
    }
  };

  const breadcrumbs = [
    { name: 'Dashboard', href: '/' },
    { name: 'Accounts' },
  ];

  const hasSelection = selectedAccountIds.length > 0;
  const allSelected = selectedAccountIds.length === accounts.length && accounts.length > 0;

  return (
    <>
      <TopBar title="Accounts" breadcrumbs={breadcrumbs} />
      
      <div className="p-6">
        {/* Actions Bar */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Button onClick={handleAddAccount} variant="primary">
              <Plus size={16} className="mr-2" />
              Add Account
            </Button>
            
            {hasSelection && (
              <>
                <Button onClick={handleBatchTweet} variant="secondary">
                  <MessageSquare size={16} className="mr-2" />
                  Tweet to {selectedAccountIds.length} Accounts
                </Button>
                <Button
                  onClick={clearAccountSelection}
                  variant="ghost"
                  size="sm"
                >
                  Clear Selection
                </Button>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Select All */}
            <button
              onClick={allSelected ? clearAccountSelection : selectAllAccounts}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
            >
              {allSelected ? <CheckSquare size={16} /> : <Square size={16} />}
              Select All
            </button>

            {/* Refresh All */}
            <Button
              onClick={handleRefreshAllTokens}
              variant="secondary"
              size="sm"
              isLoading={isRefreshingTokens}
            >
              <RefreshCw size={16} className="mr-2" />
              Refresh All
            </Button>

            {/* View Toggle */}
            <div className="flex items-center border border-border rounded-lg">
              <button
                onClick={() => setAccountViewMode('grid')}
                className={`p-2 ${
                  accountViewMode === 'grid'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Grid3x3 size={16} />
              </button>
              <button
                onClick={() => setAccountViewMode('list')}
                className={`p-2 ${
                  accountViewMode === 'list'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <List size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Accounts Grid/List */}
        {isLoadingAccounts ? (
          <div className={accountViewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6' : 'space-y-3'}>
            {[...Array(8)].map((_, i) => (
              <Skeleton key={i} className={accountViewMode === 'grid' ? 'h-80' : 'h-20'} />
            ))}
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12">
            <Users size={48} className="mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">No accounts yet</h3>
            <p className="text-muted-foreground mb-4">Add your first Twitter account to get started</p>
            <Button onClick={handleAddAccount} variant="primary">
              <Plus size={16} className="mr-2" />
              Add Account
            </Button>
          </div>
        ) : (
          <>
            {accountViewMode === 'grid' ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {accounts.map(account => (
                  <AccountCard
                    key={account.id}
                    account={account}
                    onRefreshToken={handleRefreshToken}
                    onViewTweets={handleViewTweets}
                    onNewTweet={handleNewTweet}
                  />
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {accounts.map(account => (
                  <AccountList
                    key={account.id}
                    account={account}
                    onRefreshToken={handleRefreshToken}
                    onViewTweets={handleViewTweets}
                    onNewTweet={handleNewTweet}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Compose Tweet Modal */}
      <ComposeTweetModal
        isOpen={isComposeTweetModalOpen}
        onClose={() => {
          closeComposeTweetModal();
          setSelectedAccountForTweet(null);
        }}
        onSubmit={handleComposeTweet}
        accounts={accounts}
        preselectedAccountIds={
          selectedAccountForTweet
            ? [selectedAccountForTweet.id]
            : selectedAccountIds.length > 0
            ? selectedAccountIds
            : []
        }
      />
    </>
  );
};