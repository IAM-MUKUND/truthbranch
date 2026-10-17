import React, { useState, useEffect } from 'react';
import ChatPortal from './components/ChatPortal';
import AdminConsole from './components/AdminConsole';
import { fetchHealth } from './api';

export default function App() {
  const [currentRoute, setCurrentRoute] = useState<'chat' | 'admin'>(() => {
    return window.location.pathname.startsWith('/admin') ? 'admin' : 'chat';
  });
  const [backendConnected, setBackendConnected] = useState<boolean>(true);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentRoute(window.location.pathname.startsWith('/admin') ? 'admin' : 'chat');
    };
    window.addEventListener('popstate', handlePopState);

    // Initial health check
    fetchHealth()
      .then(() => setBackendConnected(true))
      .catch(() => setBackendConnected(false));

    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  function navigateTo(route: 'chat' | 'admin') {
    setCurrentRoute(route);
    const path = route === 'admin' ? '/admin' : '/';
    if (window.location.pathname !== path) {
      window.history.pushState(null, '', path);
    }
  }

  return (
    <>
      {currentRoute === 'chat' ? (
        <ChatPortal
          onSwitchToAdmin={() => navigateTo('admin')}
          backendConnected={backendConnected}
        />
      ) : (
        <AdminConsole
          onSwitchToChat={() => navigateTo('chat')}
        />
      )}
    </>
  );
}
