import { format, formatDistance, formatRelative, isToday, isYesterday } from 'date-fns';

export function formatDate(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  
  if (isToday(d)) {
    return format(d, 'h:mm a');
  }
  
  if (isYesterday(d)) {
    return 'Yesterday ' + format(d, 'h:mm a');
  }
  
  return format(d, 'MMM d, yyyy h:mm a');
}

export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return formatDistance(d, new Date(), { addSuffix: true });
}

export function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
}

export function getAccountHealthColor(status?: string): string {
  switch (status) {
    case 'healthy':
      return 'text-green-500';
    case 'expiring':
    case 'expiring_soon':
      return 'text-yellow-500';
    case 'expired':
    case 'refresh_failed':
      return 'text-red-500';
    default:
      return 'text-gray-500';
  }
}

export function getAccountHealthBadgeClass(status?: string): string {
  switch (status) {
    case 'healthy':
      return 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400';
    case 'expiring':
    case 'expiring_soon':
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400';
    case 'expired':
    case 'refresh_failed':
      return 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-900/20 dark:text-gray-400';
  }
}

export function getTweetStatusBadgeClass(status: string): string {
  switch (status) {
    case 'posted':
      return 'bg-green-100 text-green-700 dark:bg-green-900/20 dark:text-green-400';
    case 'pending':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400';
    case 'failed':
      return 'bg-red-100 text-red-700 dark:bg-red-900/20 dark:text-red-400';
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-900/20 dark:text-gray-400';
  }
}