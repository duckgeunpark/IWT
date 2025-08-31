import React, { useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import '../styles/Header.css';

const Header = () => {
  const { loginWithRedirect, logout, isAuthenticated, user, isLoading, error } = useAuth0();

  const handleLogin = () => {
    console.log('🔐 로그인 버튼 클릭됨');
    loginWithRedirect();
  };

  const handleLogout = () => {
    console.log('🔐 로그아웃 버튼 클릭됨');
    logout({ returnTo: window.location.origin });
  };

  // Auth0 상태 변화 추적
  useEffect(() => {
    console.log('🔐 Header Auth0 Status:');
    console.log('- isLoading:', isLoading);
    console.log('- isAuthenticated:', isAuthenticated);
    console.log('- user:', user);
    console.log('- error:', error);
    
    // localStorage와 sessionStorage 확인
    console.log('🔐 Storage Debug:');
    console.log('- localStorage keys:', Object.keys(localStorage));
    console.log('- sessionStorage keys:', Object.keys(sessionStorage));
    
    // Auth0 관련 스토리지 데이터 확인
    const auth0Keys = Object.keys(localStorage).filter(key => key.includes('auth0'));
    if (auth0Keys.length > 0) {
      console.log('- Auth0 localStorage keys:', auth0Keys);
      auth0Keys.forEach(key => {
        try {
          const value = localStorage.getItem(key);
          console.log(`  - ${key}:`, JSON.parse(value));
        } catch (e) {
          const rawValue = localStorage.getItem(key);
          console.log(`  - ${key}:`, rawValue);
        }
      });
    }
  }, [isLoading, isAuthenticated, user, error]);

  if (isLoading) {
    return (
      <header className="header">
        <div className="header-left">
          <div className="logo-container">
            <div className="logo-avatar"></div>
            <div className="logo-text">
              <h1>IWT</h1>
              <p>I Want. I Went. Trip.</p>
            </div>
          </div>
        </div>
        <div className="header-right">
          <span>로딩 중...</span>
        </div>
      </header>
    );
  }

  return (
    <header className="header">
      <div className="header-left">
        <div className="logo-container">
          <div className="logo-avatar"></div>
          <div className="logo-text">
            <h1>IWT</h1>
            <p>I Want. I Went. Trip.</p>
          </div>
        </div>
      </div>
      <div className="header-right">
        {isAuthenticated ? (
          <>
            <span className="user-info">안녕하세요, {user?.name || user?.email}님!</span>
            <button className="logout-btn" onClick={handleLogout}>로그아웃</button>
            <button className="settings-btn">설정</button>
          </>
        ) : (
          <>
            <button className="login-btn" onClick={handleLogin}>로그인</button>
            <button className="settings-btn">설정</button>
          </>
        )}
      </div>
    </header>
  );
};

export default Header;