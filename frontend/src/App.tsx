import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import ProfilePage from './pages/ProfilePage';
import BidPeriodsPage from './pages/BidPeriodsPage';
import BidPeriodDetailPage from './pages/BidPeriodDetailPage';
import SequenceBrowserPage from './pages/SequenceBrowserPage';
import SequenceDetailPage from './pages/SequenceDetailPage';
import BidsPage from './pages/BidsPage';
import CalendarPage from './pages/CalendarPage';
import AwardedSchedulePage from './pages/AwardedSchedulePage';
import SequenceComparisonPage from './pages/SequenceComparisonPage';
import ExportPage from './pages/ExportPage';
import BidHistoryPage from './pages/BidHistoryPage';
import GlossaryPage from './pages/GlossaryPage';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            {/* Protected routes */}
            <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route path="/history" element={<BidHistoryPage />} />
              <Route path="/glossary" element={<GlossaryPage />} />
              <Route path="/bid-periods" element={<BidPeriodsPage />} />
              <Route path="/bid-periods/:bidPeriodId" element={<BidPeriodDetailPage />} />
              <Route path="/bid-periods/:bidPeriodId/sequences" element={<SequenceBrowserPage />} />
              <Route path="/bid-periods/:bidPeriodId/sequences/compare" element={<SequenceComparisonPage />} />
              <Route path="/bid-periods/:bidPeriodId/sequences/:sequenceId" element={<SequenceDetailPage />} />
              <Route path="/bid-periods/:bidPeriodId/bids" element={<BidsPage />} />
              <Route path="/bid-periods/:bidPeriodId/export" element={<ExportPage />} />
              <Route path="/bid-periods/:bidPeriodId/calendar" element={<CalendarPage />} />
              <Route path="/bid-periods/:bidPeriodId/awarded" element={<AwardedSchedulePage />} />
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
