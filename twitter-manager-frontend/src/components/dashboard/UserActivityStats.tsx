import React from 'react';

interface UserActivityStatsProps {
  rankings: any[];
  totalChanges: number;
  selectedListId: string;
  listName?: string;
}

export const UserActivityStats: React.FC<UserActivityStatsProps> = ({
  rankings,
  totalChanges,
  selectedListId
}) => {
  const postedCount = rankings.reduce((sum, user) => sum + user.postedCount, 0);
  
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="p-4 rounded-lg bg-purple-100/10 dark:bg-purple-900/10 backdrop-blur-sm border border-purple-200/20 dark:border-purple-700/20 text-center">
        <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
          {rankings.length}
        </div>
        <div className="text-sm text-muted-foreground">
          {selectedListId === 'all' ? 'Active Brainlifts' : 'Group Brainlifts'}
        </div>
      </div>
      <div className="p-4 rounded-lg bg-blue-100/10 dark:bg-blue-900/10 backdrop-blur-sm border border-blue-200/20 dark:border-blue-700/20 text-center">
        <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
          {totalChanges}
        </div>
        <div className="text-sm text-muted-foreground">Total Activity</div>
      </div>
      <div className="p-4 rounded-lg bg-green-100/10 dark:bg-green-900/10 backdrop-blur-sm border border-green-200/20 dark:border-green-700/20 text-center">
        <div className="text-2xl font-bold text-green-600 dark:text-green-400">
          {postedCount}
        </div>
        <div className="text-sm text-muted-foreground">Posted</div>
      </div>
    </div>
  );
};