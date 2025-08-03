import React from 'react';
import { Search, Bell, User } from 'lucide-react';
import { cn } from '../../utils/cn';

interface TopBarProps {
  title: string;
  breadcrumbs?: Array<{ name: string; href?: string }>;
}

export const TopBar: React.FC<TopBarProps> = ({ title, breadcrumbs }) => {
  return (
    <div className="bg-card border-b border-border px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          {/* Breadcrumbs */}
          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="flex items-center space-x-2 text-sm text-muted-foreground mb-1">
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={crumb.name}>
                  {index > 0 && <span>/</span>}
                  {crumb.href ? (
                    <a
                      href={crumb.href}
                      className="hover:text-foreground transition-colors"
                    >
                      {crumb.name}
                    </a>
                  ) : (
                    <span>{crumb.name}</span>
                  )}
                </React.Fragment>
              ))}
            </nav>
          )}
          
          {/* Page title */}
          <h1 className="text-2xl font-bold">{title}</h1>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative hidden md:block">
            <Search
              size={18}
              className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground"
            />
            <input
              type="text"
              placeholder="Search..."
              className="pl-10 pr-4 py-2 w-64 rounded-lg bg-background border border-border focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          {/* Notifications */}
          <button className="relative p-2 rounded-lg hover:bg-accent transition-colors">
            <Bell size={20} />
            <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full"></span>
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