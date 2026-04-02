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

const LoadingFallback = () => (
  <div className="page-loading">
    <div className="page-loading-spinner" />
    <p>페이지를 불러오는 중...</p>
  </div>
);

function TokenBridge() {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();

  useEffect(() => {
    if (isAuthenticated) {
      setTokenProvider(getAccessTokenSilently);
    }
  }, [isAuthenticated, getAccessTokenSilently]);

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
                <Route path="/trip/new" element={<NewTripPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/new/edit" element={<CreateTripPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/:id" element={<TripDetailPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/trip/:id/edit" element={<CreateTripPage toggleTheme={toggleTheme} theme={theme} />} />
                <Route path="/profile" element={<ProfilePage toggleTheme={toggleTheme} theme={theme} />} />
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
