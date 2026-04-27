import React, { useEffect, Suspense } from 'react';
import './App.css';
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/Toast';
import useTheme from './hooks/useTheme';
import { setTokenProvider } from './services/apiClient';

const MainPage = React.lazy(() => import('./pages/MainPage'));
const CreateTripPage = React.lazy(() => import('./pages/CreateTripPage'));
const NewTripPage = React.lazy(() => import('./pages/NewTripPage'));
const TripDetailPage = React.lazy(() => import('./pages/TripDetailPage'));
const ExplorePage = React.lazy(() => import('./pages/ExplorePage'));
const ProfilePage = React.lazy(() => import('./pages/ProfilePage'));
const FeedPage = React.lazy(() => import('./pages/FeedPage'));
const UserProfilePage = React.lazy(() => import('./pages/UserProfilePage'));
const AdminDashboardPage = React.lazy(() => import('./pages/AdminDashboardPage'));
const AdminSettingsPage = React.lazy(() => import('./pages/AdminSettingsPage'));
const AdminUsersPage = React.lazy(() => import('./pages/AdminUsersPage'));
const AdminPostsPage = React.lazy(() => import('./pages/AdminPostsPage'));
const AdminPlacesPage = React.lazy(() => import('./pages/AdminPlacesPage'));

const LoadingFallback = () => (
  <div className="page-loading">
    <div className="page-loading-spinner" />
    <p>페이지를 불러오는 중...</p>
  </div>
);

function TokenBridge() {
  const { getAccessTokenSilently, isAuthenticated, user } = useAuth0();

  useEffect(() => {
    if (!isAuthenticated || !user) return;
    setTokenProvider(getAccessTokenSilently);

    // 최초 로그인 시에만 DB에 저장, 이후 로그인은 확인만 (DB 변경 없음)
    // 단, picture가 NULL인 경우(버그로 저장 못 했던 기존 계정)는 한 번만 채워줌
    const ensureUserExists = async () => {
      try {
        const { apiClient } = await import('./services/apiClient');
        const meData = await apiClient.get('/api/v1/users/me');
        // 기존 사용자인데 picture가 없으면(과거 버그) 한 번만 채워줌
        if (!meData.picture && user.picture) {
          await apiClient.put(`/api/v1/users/profile/${encodeURIComponent(user.sub)}`, {
            picture: user.picture,
          }).catch(() => {});
        }
      } catch (err) {
        if (err?.status === 404 || err?.response?.status === 404 || err?.message?.includes('404')) {
          // 최초 로그인 → Auth0 데이터로 DB에 저장
          try {
            const { apiClient } = await import('./services/apiClient');
            await apiClient.post('/api/v1/users/auth0', {
              id: user.sub,
              email: user.email || `${user.sub}@unknown.com`,
              name: user.name || user.nickname || null,
              picture: user.picture || null,
            });
          } catch (createErr) {
            console.warn('User creation failed:', createErr);
          }
        }
      }
    };
    ensureUserExists();
  }, [isAuthenticated, user, getAccessTokenSilently]);

  return null;
}

function AppContent() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Router>
      <ErrorBoundary>
        <ToastProvider>
          <TokenBridge />
          <Suspense fallback={<LoadingFallback />}>
            <div className="App">
              <Routes>
                <Route path="/" element={<MainPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/explore" element={<ExplorePage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/feed" element={<FeedPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/new" element={<NewTripPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/new/edit" element={<CreateTripPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/:id" element={<TripDetailPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/:id/edit" element={<CreateTripPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/profile" element={<ProfilePage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/profile/:userId" element={<UserProfilePage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/admin" element={<AdminDashboardPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/admin/settings" element={<AdminSettingsPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/admin/users" element={<AdminUsersPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/admin/posts" element={<AdminPostsPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/admin/places" element={<AdminPlacesPage toggleTheme={toggleTheme} theme={theme} />} />
                {/* 레거시 경로 호환 */}
                <Route path="/create-trip" element={<CreateTripPage toggleTheme={toggleTheme} theme={theme} />} />
              </Routes>
            </div>
          </Suspense>
        </ToastProvider>
      </ErrorBoundary>
    </Router>
  );
}

function App() {
  return (
    <Provider store={store}>
      <Auth0Provider
        domain={process.env.REACT_APP_AUTH0_DOMAIN}
        clientId={process.env.REACT_APP_AUTH0_CLIENT_ID}
        authorizationParams={{
          redirect_uri: process.env.REACT_APP_AUTH0_CALLBACK_URL,
          audience: process.env.REACT_APP_AUTH0_AUDIENCE
        }}
      >
        <AppContent />
      </Auth0Provider>
    </Provider>
  );
}

export default App;
