import { useState, useEffect } from 'react';
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

    // Smooth SPA navigation when clicking internal route links
    const handleLinkClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest('a');
      if (!anchor) return;
      if (e.ctrlKey || e.metaKey || e.shiftKey || anchor.target === '_blank') return;
      const href = anchor.getAttribute('href');
      if (href === '/' || href === '/admin' || href?.startsWith('/admin?')) {
        e.preventDefault();
        navigateTo(href.startsWith('/admin') ? 'admin' : 'chat');
      }
    };
    document.addEventListener('click', handleLinkClick);

    // Initial health check
    fetchHealth()
      .then(() => setBackendConnected(true))
      .catch(() => setBackendConnected(false));

    return () => {
      window.removeEventListener('popstate', handlePopState);
      document.removeEventListener('click', handleLinkClick);
    };
  }, []);

  useEffect(() => {
    if (currentRoute === 'admin') {
      document.title = 'TruthBranch Governance \u2014 Admin Console (/admin)';
    } else {
      document.title = 'TruthBranch AI Assistant (/)';
    }
  }, [currentRoute]);

  function navigateTo(route: 'chat' | 'admin') {
    setCurrentRoute(route);
    const path = route === 'admin' ? '/admin' : '/';
    if (window.location.pathname !== path) {
      window.history.pushState(null, '', path);
    }
    window.scrollTo(0, 0);
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
