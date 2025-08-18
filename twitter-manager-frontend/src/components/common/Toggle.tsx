import React from 'react';

interface ToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  leftLabel?: string;
  rightLabel?: string;
  loading?: boolean;
  disabled?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'purple' | 'green' | 'blue';
  className?: string;
}

const sizeClasses = {
  sm: {
    container: 'h-4 w-8',
    circle: 'h-3 w-3',
    translateOn: 'translate-x-4',
    translateOff: 'translate-x-0.5',
  },
  md: {
    container: 'h-6 w-11',
    circle: 'h-4 w-4',
    translateOn: 'translate-x-6',
    translateOff: 'translate-x-1',
  },
  lg: {
    container: 'h-8 w-14',
    circle: 'h-6 w-6',
    translateOn: 'translate-x-7',
    translateOff: 'translate-x-1',
  },
};

const variantClasses = {
  default: {
    active: 'bg-gradient-to-r from-gray-600 to-gray-700 shadow-lg shadow-gray-500/25',
    inactive: 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600',
    labelActive: 'text-gray-600 dark:text-gray-400',
    focus: 'focus:ring-gray-500',
  },
  purple: {
    active: 'bg-gradient-to-r from-purple-500 to-pink-500 shadow-lg shadow-purple-500/25',
    inactive: 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600',
    labelActive: 'text-purple-600 dark:text-purple-400',
    focus: 'focus:ring-purple-500',
  },
  green: {
    active: 'bg-gradient-to-r from-green-500 to-emerald-500 shadow-lg shadow-green-500/25',
    inactive: 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600',
    labelActive: 'text-green-600 dark:text-green-400',
    focus: 'focus:ring-green-500',
  },
  blue: {
    active: 'bg-gradient-to-r from-blue-500 to-cyan-500 shadow-lg shadow-blue-500/25',
    inactive: 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600',
    labelActive: 'text-blue-600 dark:text-blue-400',
    focus: 'focus:ring-blue-500',
  },
};

export const Toggle: React.FC<ToggleProps> = ({
  enabled,
  onChange,
  leftLabel,
  rightLabel,
  loading = false,
  disabled = false,
  size = 'md',
  variant = 'default',
  className = '',
}) => {
  const sizeConfig = sizeClasses[size];
  const variantConfig = variantClasses[variant];

  const handleClick = () => {
    if (!disabled && !loading) {
      onChange(!enabled);
    }
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Left Label */}
      {leftLabel && (
        <span className={`text-sm font-medium transition-colors duration-300 ${
          !enabled ? variantConfig.labelActive : 'text-muted-foreground'
        }`}>
          {leftLabel}
        </span>
      )}

      {/* Toggle Switch */}
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || loading}
        className={`
          relative inline-flex ${sizeConfig.container} items-center rounded-full transition-all duration-300 
          focus:outline-none focus:ring-2 ${variantConfig.focus} focus:ring-offset-2 
          disabled:opacity-50 disabled:cursor-not-allowed
          ${enabled ? variantConfig.active : variantConfig.inactive}
        `}
        role="switch"
        aria-checked={enabled}
        aria-label={`Toggle ${leftLabel || rightLabel || 'setting'}`}
      >
        {/* Toggle Circle */}
        <span
          className={`
            inline-block ${sizeConfig.circle} transform rounded-full bg-white transition-all duration-300 ease-in-out shadow-md
            ${enabled ? sizeConfig.translateOn : sizeConfig.translateOff}
            ${loading ? 'animate-pulse' : ''}
          `}
        >
          {/* Inner glow effect when active */}
          {enabled && !loading && (
            <span className={`absolute inset-0 rounded-full transition-opacity duration-300 ${
              variant === 'purple' ? 'bg-purple-100' :
              variant === 'green' ? 'bg-green-100' :
              variant === 'blue' ? 'bg-blue-100' : 'bg-gray-100'
            } animate-pulse opacity-50`} />
          )}
        </span>
        
        {/* Loading indicator */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className={`${size === 'sm' ? 'h-1.5 w-1.5' : size === 'lg' ? 'h-3 w-3' : 'h-2 w-2'} rounded-full bg-white animate-spin border ${
              variant === 'purple' ? 'border-purple-300' :
              variant === 'green' ? 'border-green-300' :
              variant === 'blue' ? 'border-blue-300' : 'border-gray-300'
            }`} />
          </div>
        )}
      </button>

      {/* Right Label */}
      {rightLabel && (
        <span className={`text-sm font-medium transition-colors duration-300 ${
          enabled ? variantConfig.labelActive : 'text-muted-foreground'
        }`}>
          {rightLabel}
        </span>
      )}
    </div>
  );
};