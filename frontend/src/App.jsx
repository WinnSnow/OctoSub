import React from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

import AppShell from './components/AppShell';
import { useAuthSession } from './hooks/useAuthSession';
import { useTheme } from './hooks/useTheme';
import { AppRoutes } from './routes';
import SystemLoginPage from './pages/SystemLoginPage';
import './App.css';

function App() {
  const { authLoading, user, setUser, logoutUser } = useAuthSession();
  const appearanceControls = useTheme();
  const { theme, toggleTheme } = appearanceControls;

  if (authLoading) {
    return (
      <div className="auth-loading-screen">
        <div className="spinner-border text-primary" />
      </div>
    );
  }

  if (!user) {
    return (
      <>
        <Toaster position="bottom-right" />
        <SystemLoginPage onLogin={setUser} />
      </>
    );
  }

  return (
    <Router>
      <AppShell
        user={user}
        theme={theme}
        onToggleTheme={toggleTheme}
        onLogout={logoutUser}
        appearanceControls={appearanceControls}
      >
        <Toaster
          position="bottom-right"
          toastOptions={{
            duration: 3000,
            style: {
              background: 'var(--bg-surface)',
              color: 'var(--text-main)',
              border: '1px solid var(--border-soft)',
              borderRadius: '8px',
              padding: '12px 20px',
            },
          }}
        />
        <AppRoutes />
      </AppShell>
    </Router>
  );
}

export default App;
