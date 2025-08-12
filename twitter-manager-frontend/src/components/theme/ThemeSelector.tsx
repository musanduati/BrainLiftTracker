import React, { useState, useRef, useEffect } from 'react';
import { Palette, Check, Sun, Moon, Sunrise, Waves, Trees } from 'lucide-react';
import { useStore, ThemeOption } from '../../store/useStore';
import { cn } from '../../utils/cn';

interface ThemeConfig {
  name: string;
  icon: React.ReactNode;
  description: string;
  colors: {
    primary: string;
    secondary: string;
    accent: string;
  };
}

const themes: Record<ThemeOption, ThemeConfig> = {
  light: {
    name: 'Light',
    icon: <Sun size={16} />,
    description: 'Clean and bright',
    colors: {
      primary: 'bg-blue-500',
      secondary: 'bg-gray-100',
      accent: 'bg-blue-600',
    },
  },
  dark: {
    name: 'Dark',
    icon: <Moon size={16} />,
    description: 'Easy on the eyes',
    colors: {
      primary: 'bg-gray-800',
      secondary: 'bg-gray-900',
      accent: 'bg-blue-500',
    },
  },
  midnight: {
    name: 'Midnight',
    icon: <Moon size={16} className="text-indigo-400" />,
    description: 'Deep blue night',
    colors: {
      primary: 'bg-indigo-900',
      secondary: 'bg-slate-950',
      accent: 'bg-indigo-500',
    },
  },
  sunset: {
    name: 'Sunset',
    icon: <Sunrise size={16} className="text-orange-400" />,
    description: 'Warm and vibrant',
    colors: {
      primary: 'bg-orange-600',
      secondary: 'bg-pink-900',
      accent: 'bg-purple-600',
    },
  },
  ocean: {
    name: 'Ocean',
    icon: <Waves size={16} className="text-cyan-400" />,
    description: 'Cool and calm',
    colors: {
      primary: 'bg-cyan-700',
      secondary: 'bg-teal-900',
      accent: 'bg-cyan-500',
    },
  },
  forest: {
    name: 'Forest',
    icon: <Trees size={16} className="text-green-500" />,
    description: 'Natural and fresh',
    colors: {
      primary: 'bg-green-700',
      secondary: 'bg-emerald-900',
      accent: 'bg-green-500',
    },
  },
};

export const ThemeSelector: React.FC = () => {
  const { theme, setTheme } = useStore();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const currentTheme = themes[theme];

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-2 rounded-lg hover:bg-accent transition-colors"
        title="Change theme"
      >
        <Palette size={20} />
        <span className="hidden sm:inline text-sm font-medium">{currentTheme.name}</span>
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-64 bg-background border border-border rounded-lg shadow-xl z-50 overflow-hidden">
          <div className="p-2">
            <div className="text-xs font-semibold text-muted-foreground px-2 py-1 uppercase tracking-wider">
              Choose Theme
            </div>
            
            {(Object.entries(themes) as [ThemeOption, ThemeConfig][]).map(([key, config]) => (
              <button
                key={key}
                onClick={() => {
                  setTheme(key);
                  setIsOpen(false);
                }}
                className={cn(
                  "w-full flex items-start gap-3 p-3 rounded-lg transition-colors",
                  theme === key ? "bg-muted" : "hover:bg-muted/50"
                )}
              >
                <div className="flex-shrink-0 mt-0.5">
                  {config.icon}
                </div>
                
                <div className="flex-1 text-left">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-sm">{config.name}</span>
                    {theme === key && (
                      <Check size={16} className="text-green-500" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {config.description}
                  </p>
                  
                  {/* Color preview */}
                  <div className="flex gap-1 mt-2">
                    <div className={cn("w-4 h-4 rounded", config.colors.primary)} />
                    <div className={cn("w-4 h-4 rounded", config.colors.secondary)} />
                    <div className={cn("w-4 h-4 rounded", config.colors.accent)} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};