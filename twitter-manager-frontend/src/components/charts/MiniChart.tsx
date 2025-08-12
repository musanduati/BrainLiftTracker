import React from 'react';
import { cn } from '../../utils/cn';

interface MiniChartProps {
  data: number[];
  height?: number;
  width?: number;
  color?: string;
  type?: 'line' | 'bar';
  showDots?: boolean;
}

export const MiniChart: React.FC<MiniChartProps> = ({
  data,
  height = 40,
  width = 120,
  color = 'text-blue-500',
  type = 'line',
  showDots = false,
}) => {
  if (data.length === 0) return null;

  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  
  const normalizedData = data.map(value => 
    ((value - min) / range) * (height - 4)
  );

  if (type === 'bar') {
    const barWidth = width / data.length;
    
    return (
      <svg width={width} height={height} className="overflow-visible">
        {normalizedData.map((value, index) => (
          <rect
            key={index}
            x={index * barWidth + barWidth * 0.1}
            y={height - value - 2}
            width={barWidth * 0.8}
            height={value}
            className={cn("fill-current", color)}
            opacity={0.8}
          />
        ))}
      </svg>
    );
  }

  // Line chart
  const points = normalizedData
    .map((value, index) => {
      const x = (index / (data.length - 1)) * (width - 4) + 2;
      const y = height - value - 2;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        className={cn(color)}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {showDots && normalizedData.map((value, index) => {
        const x = (index / (data.length - 1)) * (width - 4) + 2;
        const y = height - value - 2;
        return (
          <circle
            key={index}
            cx={x}
            cy={y}
            r="3"
            className={cn("fill-current", color)}
          />
        );
      })}
    </svg>
  );
};