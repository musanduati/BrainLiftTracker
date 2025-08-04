import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  Users,
  List,
  Settings,
  Menu,
  X,
  Moon,
  Sun,
  ChevronLeft,
  ChevronRight,
  Shield,
} from 'lucide-react';
import { cn } from '../../utils/cn';
import { useStore } from '../../store/useStore';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Home },
  { name: 'Accounts', href: '/accounts', icon: Users },
  { name: 'Lists', href: '/lists', icon: List },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export const Sidebar: React.FC = () => {
  const location = useLocation();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const { theme, toggleTheme, isMockMode } = useStore();

  const isActive = (path: string) => location.pathname === path;

  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setIsMobileOpen(!isMobileOpen)}
        className="fixed top-4 left-4 z-50 p-2 rounded-md bg-background border border-border md:hidden"
      >
        {isMobileOpen ? <X size={20} /> : <Menu size={20} />}
      </button>

      {/* Mobile backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={cn(
          'fixed top-0 left-0 z-40 h-screen bg-card border-r border-border transition-all duration-300',
          isCollapsed ? 'w-16' : 'w-64',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <h1 className={cn('font-bold text-xl', isCollapsed && 'hidden')}>
              Brainlift Monitor
            </h1>
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              className="p-1.5 rounded-md hover:bg-accent hidden md:block"
            >
              {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-2 py-4 space-y-1">
            {navigation.map((item) => {
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg transition-colors',
                    isActive(item.href)
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent'
                  )}
                  onClick={() => setIsMobileOpen(false)}
                >
                  <Icon size={20} />
                  <span className={cn('font-medium', isCollapsed && 'hidden')}>
                    {item.name}
                  </span>
                </Link>
              );
            })}
          </nav>

          {/* Bottom section */}
          <div className="p-4 border-t border-border space-y-2">
            {/* Mock mode indicator */}
            {isMockMode && (
              <div className={cn(
                'flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-100 dark:bg-yellow-900/20',
                isCollapsed && 'justify-center'
              )}>
                <Shield size={16} className="text-yellow-600 dark:text-yellow-400" />
                {!isCollapsed && (
                  <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
                    Mock Mode
                  </span>
                )}
              </div>
            )}

            {/* Theme toggle */}
            <button
              onClick={toggleTheme}
              className={cn(
                'flex items-center gap-3 w-full px-3 py-2 rounded-lg hover:bg-accent transition-colors',
                isCollapsed && 'justify-center'
              )}
            >
              {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
              {!isCollapsed && (
                <span className="font-medium">
                  {theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
};