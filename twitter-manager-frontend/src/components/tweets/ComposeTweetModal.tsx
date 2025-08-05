import React, { useState, Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { X, Send } from 'lucide-react';
import { TwitterAccount } from '../../types';
import { Button } from '../common/Button';
import { cn } from '../../utils/cn';

interface ComposeTweetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (content: string, accountIds: number[]) => void;
  accounts: TwitterAccount[];
  preselectedAccountIds?: number[];
}

export const ComposeTweetModal: React.FC<ComposeTweetModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  accounts,
  preselectedAccountIds = [],
}) => {
  const [content, setContent] = useState('');
  const [selectedAccountIds, setSelectedAccountIds] = useState<number[]>(preselectedAccountIds);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const charCount = content.length;
  const charLimit = 280;
  const isOverLimit = charCount > charLimit;

  const handleSubmit = async () => {
    if (!content.trim() || selectedAccountIds.length === 0 || isOverLimit) return;

    setIsSubmitting(true);
    try {
      await onSubmit(content, selectedAccountIds);
      setContent('');
      setSelectedAccountIds([]);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleAccount = (accountId: number) => {
    setSelectedAccountIds(prev =>
      prev.includes(accountId)
        ? prev.filter(id => id !== accountId)
        : [...prev, accountId]
    );
  };

  const selectAll = () => {
    setSelectedAccountIds(accounts.map(account => account.id));
  };

  const deselectAll = () => {
    setSelectedAccountIds([]);
  };

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/50 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-10 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-background text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-border px-6 py-4">
                  <Dialog.Title className="text-lg font-semibold">
                    Compose Tweet
                  </Dialog.Title>
                  <button
                    onClick={onClose}
                    className="rounded-lg p-1 hover:bg-accent transition-colors"
                  >
                    <X size={20} />
                  </button>
                </div>

                {/* Content */}
                <div className="px-6 py-4">
                  {/* Account selection */}
                  <div className="mb-4">
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium">
                        Select Accounts ({selectedAccountIds.length} selected)
                      </label>
                      <div className="flex gap-2">
                        <button
                          onClick={selectAll}
                          className="text-xs text-primary hover:underline"
                        >
                          Select All
                        </button>
                        <span className="text-xs text-muted-foreground">•</span>
                        <button
                          onClick={deselectAll}
                          className="text-xs text-primary hover:underline"
                        >
                          Deselect All
                        </button>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-2 max-h-40 overflow-y-auto">
                      {accounts.map(account => (
                        <label
                          key={account.id}
                          className={cn(
                            'flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-colors',
                            selectedAccountIds.includes(account.id)
                              ? 'border-primary bg-primary/10'
                              : 'border-border hover:bg-accent'
                          )}
                        >
                          <input
                            type="checkbox"
                            checked={selectedAccountIds.includes(account.id)}
                            onChange={() => toggleAccount(account.id)}
                            className="w-4 h-4 rounded border-gray-300 text-primary focus:ring-primary"
                          />
                          <div className="flex items-center gap-2 flex-1 min-w-0">
                            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
                              {account.displayName?.[0] || account.username[0]}
                            </div>
                            <span className="truncate text-sm">@{account.username}</span>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>

                  {/* Tweet content */}
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Tweet Content
                    </label>
                    <textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      placeholder="What's happening?"
                      rows={6}
                      className={cn(
                        'w-full px-3 py-2 rounded-lg border bg-background resize-none',
                        'focus:outline-none focus:ring-2 focus:ring-ring',
                        isOverLimit ? 'border-red-500' : 'border-border'
                      )}
                    />
                    
                    {/* Character count */}
                    <div className="flex items-center justify-between mt-2">
                      <div className="text-sm text-muted-foreground">
                        {selectedAccountIds.length === 0 && 'Select at least one account'}
                      </div>
                      <div className={cn(
                        'text-sm font-medium',
                        isOverLimit ? 'text-red-500' : charCount > 260 ? 'text-yellow-500' : 'text-muted-foreground'
                      )}>
                        {charCount} / {charLimit}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 border-t border-border px-6 py-4">
                  <Button
                    variant="ghost"
                    onClick={onClose}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    onClick={handleSubmit}
                    disabled={!content.trim() || selectedAccountIds.length === 0 || isOverLimit || isSubmitting}
                    isLoading={isSubmitting}
                  >
                    <Send size={16} className="mr-2" />
                    Tweet to {selectedAccountIds.length} {selectedAccountIds.length === 1 ? 'Account' : 'Accounts'}
                  </Button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};