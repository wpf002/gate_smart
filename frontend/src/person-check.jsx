// Throwaway harness. Not shipped.
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import './styles/globals.css';
import PersonDetailPage from './pages/PersonDetailPage';
import { useAppStore } from './store';
useAppStore.setState({ authToken: 'preview' });
useAppStore.subscribe((s) => { if (!s.authToken) useAppStore.setState({ authToken: 'preview' }); });
const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
function Harness() {
  const [path] = useState(new URLSearchParams(location.search).get('p') || '/trainer/Jamie%20Ness');
  return (
    <MemoryRouter initialEntries={[path]}>
      <div className="app-shell"><div className="page-content">
        <Routes>
          <Route path="/trainer/:name" element={<PersonDetailPage type="trainer" />} />
          <Route path="/jockey/:name" element={<PersonDetailPage type="jockey" />} />
        </Routes>
      </div></div>
    </MemoryRouter>
  );
}
createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={qc}><Harness /></QueryClientProvider>);
