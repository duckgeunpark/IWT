import './App.css';
import MainPage from './pages/MainPage';
import CreateTripPage from './pages/CreateTripPage';
import { Auth0Provider } from '@auth0/auth0-react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/Toast';
import useTheme from './hooks/useTheme';

function AppContent() {
  const { theme, toggleTheme } = useTheme();

  return (
    <Router>
      <ErrorBoundary>
        <ToastProvider>
          <div className="App">
            <Routes>
              <Route path="/" element={<MainPage toggleTheme={toggleTheme} theme={theme} />} />
              <Route path="/create-trip" element={<CreateTripPage toggleTheme={toggleTheme} theme={theme} />} />
            </Routes>
          </div>
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
