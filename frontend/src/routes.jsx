import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import ChannelConfigPage from './pages/ChannelConfigPage';
import DashboardPage from './pages/DashboardPage';
import DownloadHistoryPage from './pages/DownloadHistoryPage';
import LibraryPage from './pages/LibraryPage';
import JellyfinConfigPage from './pages/JellyfinConfigPage';
import PendingTransfersPage from './pages/PendingTransfersPage';
import ProxyConfigPage from './pages/ProxyConfigPage';
import RecommendationsPage from './pages/RecommendationsPage';
import SearchPage from './pages/SearchPage';
import SubscriptionsPage from './pages/SubscriptionsPage';
import SystemStatusPage from './pages/SystemStatusPage';
import TasksPage from './pages/TasksPage';
import TelegramLoginPage from './pages/TelegramLoginPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/search" element={<SearchPage />} />
      <Route path="/library" element={<LibraryPage />} />
      <Route path="/recommendations" element={<RecommendationsPage />} />
      <Route path="/subscriptions" element={<SubscriptionsPage />} />
      <Route path="/pending" element={<PendingTransfersPage />} />
      <Route path="/history" element={<DownloadHistoryPage />} />
      <Route path="/tasks" element={<TasksPage />} />
      <Route path="/system" element={<SystemStatusPage />} />
      <Route path="/channels" element={<ChannelConfigPage />} />
      <Route path="/jellyfin" element={<JellyfinConfigPage />} />
      <Route path="/proxy" element={<ProxyConfigPage />} />
      <Route path="/login" element={<TelegramLoginPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
