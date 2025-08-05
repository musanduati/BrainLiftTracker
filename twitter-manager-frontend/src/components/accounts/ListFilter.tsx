import React from 'react';
import { Filter } from 'lucide-react';
import { TwitterList } from '../../types';

interface ListFilterProps {
  lists: TwitterList[];
  selectedListId: string | null;
  onSelectList: (listId: string | null) => void;
  accountCounts?: Record<string, number>;
}

export const ListFilter: React.FC<ListFilterProps> = ({
  lists,
  selectedListId,
  onSelectList,
  accountCounts = {}
}) => {
  // Calculate total accounts
  const totalAccounts = Object.values(accountCounts).reduce((sum, count) => sum + count, 0);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Filter size={20} className="text-muted-foreground" />
      <span className="text-sm font-medium">Filter by List:</span>
      
      <div className="flex gap-2 flex-wrap">
        {/* All Accounts */}
        <button
          onClick={() => onSelectList(null)}
          className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
            selectedListId === null
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted hover:bg-muted/80 text-foreground'
          }`}
        >
          All Accounts ({totalAccounts})
        </button>

        {/* List Filters */}
        {lists.map((list) => {
          const count = accountCounts[list.id] || 0;
          return (
            <button
              key={list.id}
              onClick={() => onSelectList(list.id)}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                selectedListId === list.id
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted hover:bg-muted/80 text-foreground'
              }`}
            >
              {list.name} ({count})
            </button>
          );
        })}

        {/* Unassigned */}
        <button
          onClick={() => onSelectList('unassigned')}
          className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
            selectedListId === 'unassigned'
              ? 'bg-primary text-primary-foreground'
              : 'bg-muted hover:bg-muted/80 text-foreground'
          }`}
        >
          Unassigned ({accountCounts.unassigned || 0})
        </button>
      </div>
    </div>
  );
};