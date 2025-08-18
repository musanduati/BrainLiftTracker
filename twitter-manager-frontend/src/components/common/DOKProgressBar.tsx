import React from 'react';
import { DOKBreakdown } from '../../types';

interface DOKProgressBarProps {
  dokBreakdown: DOKBreakdown;
  totalTweets: number;
  className?: string;
  showPercentage?: boolean;
  height?: 'sm' | 'md' | 'lg';
}

export const DOKProgressBar: React.FC<DOKProgressBarProps> = ({
  dokBreakdown,
  totalTweets,
  className = '',
  showPercentage = false,
  height = 'md'
}) => {
  // Calculate percentages for each segment
  const totalChanges = dokBreakdown.dok3.total + dokBreakdown.dok4.total;
  const regularPosts = Math.max(0, totalTweets - totalChanges);
  
  const dok3AddedPct = totalTweets > 0 ? (dokBreakdown.dok3.added / totalTweets) * 100 : 0;
  const dok3DeletedPct = totalTweets > 0 ? (dokBreakdown.dok3.deleted / totalTweets) * 100 : 0;
  const dok3UpdatedPct = totalTweets > 0 ? ((dokBreakdown.dok3.updated || 0) / totalTweets) * 100 : 0;
  const dok4AddedPct = totalTweets > 0 ? (dokBreakdown.dok4.added / totalTweets) * 100 : 0;
  const dok4DeletedPct = totalTweets > 0 ? (dokBreakdown.dok4.deleted / totalTweets) * 100 : 0;
  const dok4UpdatedPct = totalTweets > 0 ? ((dokBreakdown.dok4.updated || 0) / totalTweets) * 100 : 0;
  const regularPct = totalTweets > 0 ? (regularPosts / totalTweets) * 100 : 0;

  // Height classes
  const heightClasses = {
    sm: 'h-4',
    md: 'h-6', 
    lg: 'h-8'
  };

  // Enhanced color palette for better visual appeal and distinction
  const colors = {
    // DOK3 Family - Nature/Growth themed (Greens & Earth tones)
    dok3Added: 'linear-gradient(135deg, #10B981 0%, #059669 50%, #047857 100%)', // Rich Emerald
    dok3Updated: 'linear-gradient(135deg, #22D3EE 0%, #06B6D4 50%, #0891B2 100%)', // Bright Cyan
    dok3Deleted: 'linear-gradient(135deg, #F97316 0%, #EA580C 50%, #C2410C 100%)', // Warm Orange
    
    // DOK4 Family - Sky/Technology themed (Blues & Purples)
    dok4Added: 'linear-gradient(135deg, #6366F1 0%, #4F46E5 50%, #4338CA 100%)', // Rich Indigo
    dok4Updated: 'linear-gradient(135deg, #8B5CF6 0%, #7C3AED 50%, #6D28D9 100%)', // Vibrant Purple
    dok4Deleted: 'linear-gradient(135deg, #EC4899 0%, #DB2777 50%, #BE185D 100%)', // Bright Pink
    
    // Regular posts - Neutral but elegant
    regular: 'linear-gradient(135deg, #64748B 0%, #475569 50%, #334155 100%)' // Sophisticated Slate
  };

  // Only show segments that have content
  const segments = [
    { width: dok4AddedPct, color: colors.dok4Added, label: 'DOK4 Added', count: dokBreakdown.dok4.added, emoji: '🟢' },
    { width: dok4UpdatedPct, color: colors.dok4Updated, label: 'DOK4 Updated', count: dokBreakdown.dok4.updated || 0, emoji: '🔄' },
    { width: dok4DeletedPct, color: colors.dok4Deleted, label: 'DOK4 Deleted', count: dokBreakdown.dok4.deleted, emoji: '❌' },
    { width: dok3AddedPct, color: colors.dok3Added, label: 'DOK3 Added', count: dokBreakdown.dok3.added, emoji: '🟢' },
    { width: dok3UpdatedPct, color: colors.dok3Updated, label: 'DOK3 Updated', count: dokBreakdown.dok3.updated || 0, emoji: '🔄' },
    { width: dok3DeletedPct, color: colors.dok3Deleted, label: 'DOK3 Deleted', count: dokBreakdown.dok3.deleted, emoji: '❌' },
    { width: regularPct, color: colors.regular, label: 'Regular Posts', count: regularPosts, emoji: '📝' }
  ].filter(segment => segment.width > 0);

  if (totalTweets === 0) {
    return (
      <div className={`w-full ${heightClasses[height]} bg-gray-200 dark:bg-gray-800 rounded-full ${className}`}>
        <div className="flex items-center justify-center h-full text-xs text-gray-500">
          No activity
        </div>
      </div>
    );
  }

  return (
    <div className={`group relative w-full ${heightClasses[height]} ${className}`}>
      {/* Progress bar container */}
      <div className="w-full h-full bg-gradient-to-r from-gray-200/30 to-gray-200/50 dark:from-gray-800/30 dark:to-gray-800/50 rounded-full overflow-hidden backdrop-blur-sm group-hover:from-gray-200/50 group-hover:to-gray-200/70 dark:group-hover:from-gray-800/50 dark:group-hover:to-gray-800/70 transition-all duration-300">
        
        {/* Segments */}
        <div className="flex h-full w-full">
          {segments.map((segment, index) => (
            <div
              key={index}
              className="relative transition-all duration-700 ease-out"
              style={{
                width: `${segment.width}%`,
                background: segment.color,
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.3)'
              }}
            >
              {/* Shimmer effect on hover */}
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500">
                <div className="h-full w-full bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
              </div>
            </div>
          ))}
        </div>

        {/* Show percentage if requested and bar is wide enough */}
        {showPercentage && totalChanges > 0 && (
          <div className="absolute left-2 top-1/2 -translate-y-1/2 text-white text-xs font-semibold drop-shadow-lg">
            {Math.round((totalChanges / totalTweets) * 100)}%
          </div>
        )}
      </div>

      {/* Enhanced tooltip on hover */}
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50">
        <div className="bg-gray-900/95 text-white text-xs px-3 py-2 rounded-lg shadow-xl backdrop-blur-sm whitespace-nowrap">
          <div className="font-semibold mb-1">DOK Activity Breakdown:</div>
          {segments.map((segment, index) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <span>{segment.emoji} {segment.label}:</span>
              <span className="font-medium">{segment.count} ({Math.round(segment.width)}%)</span>
            </div>
          ))}
          <div className="border-t border-gray-600 mt-1 pt-1 font-medium">
            Total: {totalTweets} posts
          </div>
        </div>
        {/* Tooltip arrow */}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900/95" />
      </div>
    </div>
  );
};

// Legend component to show color meanings
export const DOKLegend: React.FC<{ className?: string }> = ({ className = '' }) => {
  const legendItems = [
    // DOK4 Family - Sky/Technology themed
    { color: '#6366F1', label: 'DOK4 Added', emoji: '🟢', description: 'New DOK4 content' },
    { color: '#8B5CF6', label: 'DOK4 Updated', emoji: '🔄', description: 'Modified DOK4 content' },
    { color: '#EC4899', label: 'DOK4 Deleted', emoji: '❌', description: 'Removed DOK4 content' },
    
    // DOK3 Family - Nature/Growth themed  
    { color: '#10B981', label: 'DOK3 Added', emoji: '🟢', description: 'New DOK3 content' },
    { color: '#22D3EE', label: 'DOK3 Updated', emoji: '🔄', description: 'Modified DOK3 content' },
    { color: '#F97316', label: 'DOK3 Deleted', emoji: '❌', description: 'Removed DOK3 content' },
    
    // Regular posts
    { color: '#64748B', label: 'Regular Posts', emoji: '📝', description: 'Non-DOK content' }
  ];

  return (
    <div className={`${className}`}>
      {/* DOK4 Family */}
      <div className="mb-3">
        <h4 className="text-sm font-medium mb-2 text-indigo-600 dark:text-indigo-400">DOK4 - Advanced Knowledge</h4>
        <div className="flex flex-wrap gap-3 text-xs">
          {legendItems.slice(0, 3).map((item, index) => (
            <div key={index} className="flex items-center gap-1.5">
              <div 
                className="w-3 h-3 rounded-sm shadow-sm" 
                style={{ backgroundColor: item.color }}
              />
              <span className="text-muted-foreground">
                {item.emoji} {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
      
      {/* DOK3 Family */}
      <div className="mb-3">
        <h4 className="text-sm font-medium mb-2 text-emerald-600 dark:text-emerald-400">DOK3 - Applied Knowledge</h4>
        <div className="flex flex-wrap gap-3 text-xs">
          {legendItems.slice(3, 6).map((item, index) => (
            <div key={index + 3} className="flex items-center gap-1.5">
              <div 
                className="w-3 h-3 rounded-sm shadow-sm" 
                style={{ backgroundColor: item.color }}
              />
              <span className="text-muted-foreground">
                {item.emoji} {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
      
      {/* Regular Posts */}
      <div>
        <h4 className="text-sm font-medium mb-2 text-slate-600 dark:text-slate-400">Other Content</h4>
        <div className="flex flex-wrap gap-3 text-xs">
          {legendItems.slice(6).map((item, index) => (
            <div key={index + 6} className="flex items-center gap-1.5">
              <div 
                className="w-3 h-3 rounded-sm shadow-sm" 
                style={{ backgroundColor: item.color }}
              />
              <span className="text-muted-foreground">
                {item.emoji} {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};