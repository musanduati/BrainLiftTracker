export const getAvatarColor = (username: string): string => {
  const colors = [
    'from-blue-400 to-blue-600',
    'from-purple-400 to-purple-600',
    'from-green-400 to-green-600',
    'from-red-400 to-red-600',
    'from-yellow-400 to-yellow-600',
    'from-pink-400 to-pink-600',
    'from-indigo-400 to-indigo-600',
    'from-teal-400 to-teal-600',
    'from-orange-400 to-orange-600',
    'from-cyan-400 to-cyan-600',
    'from-rose-400 to-rose-600',
    'from-emerald-400 to-emerald-600',
    'from-violet-400 to-violet-600',
    'from-fuchsia-400 to-fuchsia-600',
    'from-sky-400 to-sky-600',
    'from-lime-400 to-lime-600',
  ];
  
  // Generate a hash from the username
  let hash = 0;
  for (let i = 0; i < username.length; i++) {
    hash = username.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  // Use the hash to select a color
  const index = Math.abs(hash) % colors.length;
  return colors[index];
};

export const getAvatarText = (username: string, displayName?: string): string => {
  // Try to use initials from display name if available
  if (displayName && displayName.trim()) {
    const parts = displayName.trim().split(' ');
    if (parts.length >= 2) {
      // Use first letter of first and last name
      return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
  }
  
  // Check if username has underscore (first_last format)
  if (username.includes('_')) {
    const parts = username.split('_');
    if (parts.length >= 2 && parts[0] && parts[1]) {
      // Use first letter of each part
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
  }
  
  // Otherwise use first two characters of username
  return username.substring(0, 2).toUpperCase();
};