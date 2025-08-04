import React from 'react';
import { Outlet } from 'react-router-dom';

export const Layout: React.FC = () => {
  return (
    <div className="min-h-screen bg-background">
      <main className="transition-all duration-300">
        <Outlet />
      </main>
    </div>
  );
};