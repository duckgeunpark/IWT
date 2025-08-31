import './App.css';
import MainPage from './pages/MainPage';
import CreateTripPage from './pages/CreateTripPage';
import { Auth0Provider } from '@auth0/auth0-react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store';

function App() {
  // Auth0 설정 디버깅
  console.log('🔐 Auth0 환경변수 확인:');
  console.log('- REACT_APP_AUTH0_DOMAIN:', process.env.REACT_APP_AUTH0_DOMAIN);
  console.log('- REACT_APP_AUTH0_CLIENT_ID:', process.env.REACT_APP_AUTH0_CLIENT_ID);
  console.log('- REACT_APP_AUTH0_CALLBACK_URL:', process.env.REACT_APP_AUTH0_CALLBACK_URL);
  console.log('- REACT_APP_AUTH0_AUDIENCE:', process.env.REACT_APP_AUTH0_AUDIENCE);
  
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
        <Router>
          <div className="App">
            <Routes>
              <Route path="/" element={<MainPage />} />
              <Route path="/create-trip" element={<CreateTripPage />} />
            </Routes>
          </div>
        </Router>
      </Auth0Provider>
    </Provider>
  );
}

export default App;
