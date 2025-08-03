import React from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { cn } from '../../utils/cn';

export const Layout: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className={cn(
        'transition-all duration-300',
        'md:ml-64' // Adjust based on sidebar width
      )}>
        <Outlet />
      </main>
    </div>
  );
};