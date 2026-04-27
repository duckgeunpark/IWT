import React from 'react';
import { NavLink } from 'react-router-dom';
import Header from './Header';
import '../styles/AdminLayout.css';

const NAV_ITEMS = [
  { to: '/admin',         label: '대시보드', icon: '◆', exact: true },
  { to: '/admin/users',   label: '사용자',   icon: '◉' },
  { to: '/admin/posts',   label: '게시글',   icon: '▤' },
  { to: '/admin/places',  label: 'Place',    icon: '◇' },
  { to: '/admin/settings',label: '설정',     icon: '⚙' },
];

export default function AdminLayout({ toggleTheme, theme, children, title, subtitle }) {
  return (
    <div className="admin-page">
      <Header toggleTheme={toggleTheme} theme={theme} />
      <div className="admin-layout">
        <aside className="admin-sidebar">
          <div className="admin-sidebar-title">관리자</div>
          <nav className="admin-sidebar-nav">
            {NAV_ITEMS.map(item => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.exact}
                className={({ isActive }) => `admin-nav-link ${isActive ? 'active' : ''}`}
              >
                <span className="admin-nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="admin-main">
          {(title || subtitle) && (
            <div className="admin-header">
              {title && <h1>{title}</h1>}
              {subtitle && <p className="admin-subtitle">{subtitle}</p>}
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
