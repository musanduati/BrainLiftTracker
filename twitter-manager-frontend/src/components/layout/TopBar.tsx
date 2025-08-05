import React from 'react';
import { Link } from 'react-router-dom';
import { Bell, User, Moon, Sun, Shield } from 'lucide-react';
import { useStore } from '../../store/useStore';

export const TopBar: React.FC = () => {
  const { theme, toggleTheme, isMockMode } = useStore();

  return (
    <div className="bg-card border-b border-border px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          {/* App Name */}
          <Link to="/" className="font-bold text-3xl hover:opacity-80 transition-opacity">
            Brainlift Monitor
          </Link>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Mock mode indicator */}
          {isMockMode && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-yellow-100 dark:bg-yellow-900/20">
              <Shield size={16} className="text-yellow-600 dark:text-yellow-400" />
              <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
                Mock Mode
              </span>
            </div>
          )}


          {/* Notifications */}
          <button className="relative p-2 rounded-lg hover:bg-accent transition-colors">
            <Bell size={20} />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
          </button>

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="p-2 rounded-lg hover:bg-accent transition-colors"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          </button>

          {/* User menu */}
          <button className="flex items-center gap-2 p-2 rounded-lg hover:bg-accent transition-colors">
            <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
              <User size={16} className="text-primary-foreground" />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
};