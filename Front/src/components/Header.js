import React from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import '../styles/Header.css';

const Header = ({ toggleTheme, theme }) => {
  const { loginWithRedirect, logout, isAuthenticated, user, isLoading } = useAuth0();

  const handleLogin = () => {
    loginWithRedirect();
  };

  const handleLogout = () => {
    logout({ returnTo: window.location.origin });
  };

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
        {toggleTheme && (
          <button className="theme-toggle" onClick={toggleTheme} title={theme === 'light' ? '다크 모드' : '라이트 모드'}>
            {theme === 'light' ? '\uD83C\uDF19' : '\u2600\uFE0F'}
          </button>
        )}
        {isAuthenticated ? (
          <>
            <span className="user-info">안녕하세요, {user?.name || user?.email}님!</span>
            <button className="logout-btn" onClick={handleLogout}>로그아웃</button>
          </>
        ) : (
          <button className="login-btn" onClick={handleLogin}>로그인</button>
        )}
      </div>
    </header>
  );
};

export default Header;