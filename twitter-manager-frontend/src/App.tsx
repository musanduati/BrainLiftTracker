import { useEffect, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { Layout } from './components/layout/Layout';
import { Dashboard } from './pages/Dashboard';
import { Accounts } from './pages/Accounts';
import { AccountDetail } from './pages/AccountDetail';
import { InactiveAccounts } from './pages/InactiveAccounts';
import { Lists } from './pages/Lists';
import { ListMembers } from './pages/ListMembers';
import { useStore } from './store/useStore';
import { notificationPoller } from './services/notificationPoller';
import { DOKProgressBarTest } from './components/test/DOKProgressBarTest';

// Lazy load the Analytics page to reduce initial bundle size
const Analytics = lazy(() => import('./pages/Analytics').then(module => ({ default: module.Analytics })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  const { theme } = useStore();

  useEffect(() => {
    // Apply theme on mount and when it changes
    const themes = ['light', 'dark', 'midnight', 'sunset', 'ocean', 'forest'];
    
    // Remove all theme classes
    document.documentElement.classList.remove(...themes);
    
    // Add current theme class
    document.documentElement.classList.add(theme);
    
    // If no theme was previously set, save midnight as default
    if (!localStorage.getItem('theme')) {
      localStorage.setItem('theme', 'midnight');
    }
  }, [theme]);

  useEffect(() => {
    // Start notification polling when app mounts
    notificationPoller.start();

    // Cleanup on unmount
    return () => {
      notificationPoller.stop();
    };
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="accounts" element={<Accounts />} />
            <Route path="accounts/:id" element={<AccountDetail />} />
            <Route path="accounts/inactive" element={<InactiveAccounts />} />
            <Route path="lists" element={<Lists />} />
            <Route path="lists/:listId" element={<ListMembers />} />
            <Route path="analytics" element={
              <Suspense fallback={
                <div className="flex items-center justify-center h-64">
                  <div className="text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
                    <p className="mt-4 text-muted-foreground">Loading analytics...</p>
                  </div>
                </div>
              }>
                <Analytics />
              </Suspense>
            } />
            {/* DOK Test Route - For Development Only */}
            <Route path="test/dok-progress" element={<DOKProgressBarTest />} />
          </Route>
        </Routes>
      </BrowserRouter>
      
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: theme === 'dark' ? '#1f2937' : '#ffffff',
            color: theme === 'dark' ? '#f9fafb' : '#111827',
            border: `1px solid ${theme === 'dark' ? '#374151' : '#e5e7eb'}`,
          },
          success: {
            iconTheme: {
              primary: '#10b981',
              secondary: '#ffffff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#ffffff',
            },
          },
        }}
      />
    </QueryClientProvider>
  );
}

export default App;
