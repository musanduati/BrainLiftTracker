import React, { useMemo } from 'react';
import { format, addDays, subDays } from 'date-fns';
import { cn } from '../../utils/cn';

interface ActivityData {
  date: string;
  count: number;
}

interface ActivityHeatmapProps {
  data: ActivityData[];
  weeks?: number;
}

export const ActivityHeatmap: React.FC<ActivityHeatmapProps> = ({ data, weeks = 12 }) => {
  const heatmapData = useMemo(() => {
    const today = new Date();
    const weeksToShow = weeks;
    
    // Create a map of date to count
    const dataMap = new Map<string, number>();
    data.forEach(item => {
      dataMap.set(item.date, item.count);
    });
    
    type CellData = {
      date: Date;
      count: number;
      week: number;
      day: number;
      isFuture: boolean;
    };
    
    // Generate grid structure - always create full grid
    const grid: CellData[][] = [];
    
    // Start from weeks ago, aligned to Sunday
    const todayDayOfWeek = today.getDay();
    const endDate = today;
    const daysBack = (weeksToShow * 7) - todayDayOfWeek - 1;
    const startDate = subDays(endDate, daysBack);
    
    // Create the grid week by week
    for (let w = 0; w < weeksToShow; w++) {
      const weekData: CellData[] = [];
      
      for (let d = 0; d < 7; d++) {
        const currentDate = addDays(startDate, w * 7 + d);
        const dateStr = format(currentDate, 'yyyy-MM-dd');
        
        const cellData: CellData = {
          date: currentDate,
          count: dataMap.get(dateStr) || 0,
          week: w,
          day: d,
          isFuture: currentDate > today
        };
        
        weekData.push(cellData);
      }
      
      grid.push(weekData);
    }
    
    // Flatten for compatibility but keep grid structure info
    return grid.flat();
  }, [data, weeks]);

  const maxCount = Math.max(...heatmapData.map(d => d.count), 1);
  
  const getIntensity = (count: number): string => {
    if (count === 0) return 'bg-muted';
    const intensity = count / maxCount;
    if (intensity <= 0.25) return 'bg-green-300 dark:bg-green-900';
    if (intensity <= 0.5) return 'bg-green-400 dark:bg-green-700';
    if (intensity <= 0.75) return 'bg-green-500 dark:bg-green-600';
    return 'bg-green-600 dark:bg-green-500';
  };

  // GitHub uses Mon, Wed, Fri labels
  const dayLabels = ['', 'Mon', '', 'Wed', '', 'Fri', ''];

  // Get month labels for the top
  const monthLabels = useMemo(() => {
    const labels: { week: number; label: string }[] = [];
    let lastMonth = -1;
    
    heatmapData.forEach(cell => {
      if (cell.week === 0 || cell.day === 0) {
        const month = cell.date.getMonth();
        if (month !== lastMonth) {
          labels.push({
            week: cell.week,
            label: format(cell.date, 'MMM')
          });
          lastMonth = month;
        }
      }
    });
    
    return labels;
  }, [heatmapData]);

  return (
    <div className="flex flex-col gap-2 w-full">
      {/* Month labels at the top */}
      <div className="flex gap-2">
        <div className="w-10" /> {/* Spacer for day labels */}
        <div className="flex relative">
          {monthLabels.map((label, idx) => (
            <div
              key={idx}
              className="absolute text-[10px] text-muted-foreground"
              style={{ left: `${label.week * 14}px` }}
            >
              {label.label}
            </div>
          ))}
        </div>
      </div>
      
      {/* Main heatmap */}
      <div className="flex gap-2">
        {/* Day labels on the left */}
        <div className="flex flex-col gap-[3px] text-[10px] text-muted-foreground w-10">
          {dayLabels.map((day, i) => (
            <div key={i} className="h-[11px] flex items-center justify-end pr-2">
              {day}
            </div>
          ))}
        </div>
      
      {/* Heatmap grid */}
      <div className="flex-1">
        <div className="flex gap-[3px]">
          {Array.from({ length: weeks }, (_, weekIndex) => (
            <div key={weekIndex} className="flex flex-col gap-[3px]">
              {Array.from({ length: 7 }, (_, dayIndex) => {
                const cell = heatmapData.find(d => d.week === weekIndex && d.day === dayIndex);
                
                // Always render a cell, even if empty
                if (!cell) {
                  return <div key={dayIndex} className="w-[11px] h-[11px]" />;
                }
                
                return (
                  <div
                    key={dayIndex}
                    className={cn(
                      "w-[11px] h-[11px] rounded-sm transition-all",
                      cell.isFuture ? "bg-transparent" : getIntensity(cell.count),
                      !cell.isFuture && cell.count > 0 && "hover:ring-1 hover:ring-primary cursor-pointer"
                    )}
                    title={!cell.isFuture ? `${format(cell.date, 'MMM d, yyyy')}: ${cell.count} posts` : ""}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      </div>
      
      {/* Legend - GitHub style */}
      <div className="flex items-center gap-3 justify-end mt-2">
        <span className="text-xs text-muted-foreground">Less</span>
        <div className="flex gap-1">
          <div className="w-3 h-3 bg-muted rounded-sm" title="0 contributions" />
          <div className="w-3 h-3 bg-green-300 dark:bg-green-900 rounded-sm" title="1-2 contributions" />
          <div className="w-3 h-3 bg-green-400 dark:bg-green-700 rounded-sm" title="3-4 contributions" />
          <div className="w-3 h-3 bg-green-500 dark:bg-green-600 rounded-sm" title="5-6 contributions" />
          <div className="w-3 h-3 bg-green-600 dark:bg-green-500 rounded-sm" title="7+ contributions" />
        </div>
        <span className="text-xs text-muted-foreground">More</span>
      </div>
    </div>
  );
};