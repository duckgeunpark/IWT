import React from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useNavigate, useLocation } from 'react-router-dom';
import NotificationDropdown from './NotificationDropdown';
import '../styles/Header.css';

const Header = ({ toggleTheme, theme }) => {
  const { loginWithRedirect, logout, isAuthenticated, user, isLoading } = useAuth0();
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <header className="header">
      {/* Left: Logo */}
      <div className="header-left">
        <div className="logo-container" onClick={() => navigate('/')}>
          <div className="logo-avatar"></div>
          <div className="logo-text">
            <h1>IWT</h1>
          </div>
        </div>
      </div>

      {/* Center: Navigation */}
      <nav className="header-nav">
        {/* 홈 */}
        <button
          className={`nav-item ${isActive('/') ? 'active' : ''}`}
          onClick={() => navigate('/')}
          title="홈"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill={isActive('/') ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          <span className="nav-label">홈</span>
        </button>

        {/* 탐색 — /explore, 전체 공개 여행 검색/탐색 */}
        <button
          className={`nav-item ${isActive('/explore') ? 'active' : ''}`}
          onClick={() => navigate('/explore')}
          title="탐색"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span className="nav-label">탐색</span>
        </button>

        {/* 팔로잉 — /feed, 내가 팔로우한 사람들의 여행 */}
        <button
          className={`nav-item ${isActive('/feed') ? 'active' : ''}`}
          onClick={() => {
            if (!isAuthenticated) {
              loginWithRedirect();
              return;
            }
            navigate('/feed');
          }}
          title="팔로잉"
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill={isActive('/feed') ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <span className="nav-label">팔로잉</span>
        </button>

        {/* 만들기 */}
        <button
          className="nav-item nav-create"
          onClick={() => navigate('/trip/new')}
          title="새 여행"
        >
          <div className="nav-create-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </div>
          <span className="nav-label">만들기</span>
        </button>

        {/* 프로필 */}
        <button
          className={`nav-item ${isActive('/profile') ? 'active' : ''}`}
          onClick={() => {
            if (!isAuthenticated) {
              loginWithRedirect();
              return;
            }
            navigate('/profile');
          }}
          title="프로필"
        >
          {isAuthenticated && user?.picture ? (
            <div className={`nav-profile-ring ${isActive('/profile') ? 'active' : ''}`}>
              <img src={user.picture} alt="" className="nav-profile-img" />
            </div>
          ) : (
            <svg width="22" height="22" viewBox="0 0 24 24" fill={isActive('/profile') ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          )}
          <span className="nav-label">프로필</span>
        </button>
      </nav>

      {/* Right: Actions */}
      <div className="header-right">
        {toggleTheme && (
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'light' ? '다크 모드' : '라이트 모드'}
          >
            {theme === 'light' ? '\uD83C\uDF19' : '\u2600\uFE0F'}
          </button>
        )}
        {isAuthenticated && <NotificationDropdown />}
        {isLoading ? (
          <span className="header-loading">...</span>
        ) : isAuthenticated ? (
          <button className="logout-btn" onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}>
            로그아웃
          </button>
        ) : (
          <button className="login-btn" onClick={() => loginWithRedirect()}>
            로그인
          </button>
        )}
      </div>
    </header>
  );
};

export default Header;
