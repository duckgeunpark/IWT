import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';
import AdminLayout from '../components/AdminLayout';
import '../styles/AdminDashboardPage.css';

export default function AdminDashboardPage({ toggleTheme, theme }) {
  const { isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadStats = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await apiClient.get('/api/v1/admin/stats');
      setStats(data);
    } catch (err) {
      if (err?.status === 403) setError('관리자 권한이 없습니다.');
      else setError(err?.message || '통계를 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/');
      return;
    }
    if (isAuthenticated) loadStats();
  }, [isAuthenticated, isLoading, navigate, loadStats]);

  if (isLoading) return <div className="admin-loading">로딩 중...</div>;

  return (
    <AdminLayout toggleTheme={toggleTheme} theme={theme} title="대시보드" subtitle="시스템 현황 요약">
      {error && <div className="admin-error">{error}</div>}

      {loading && <div className="admin-dashboard-loading">통계 불러오는 중...</div>}

      {stats && (
        <div className="admin-dashboard-grid">
          <Link to="/admin/users" className="admin-stat-card">
            <div className="admin-stat-label">사용자</div>
            <div className="admin-stat-value">{stats.users_total.toLocaleString()}</div>
            <div className="admin-stat-detail">
              <span className="active">활성 {stats.users_active}</span>
              <span className="muted">비활성 {stats.users_inactive}</span>
            </div>
          </Link>

          <Link to="/admin/posts" className="admin-stat-card">
            <div className="admin-stat-label">게시글</div>
            <div className="admin-stat-value">{stats.posts_total.toLocaleString()}</div>
            <div className="admin-stat-detail">
              <span className="active">공개 {stats.posts_published}</span>
              <span className="muted">초안 {stats.posts_draft}</span>
              {stats.posts_deleted > 0 && <span className="warn">삭제 {stats.posts_deleted}</span>}
            </div>
          </Link>

          <Link to="/admin/places" className="admin-stat-card">
            <div className="admin-stat-label">Place</div>
            <div className="admin-stat-value">{stats.places_total.toLocaleString()}</div>
            <div className="admin-stat-detail">
              {stats.places_missing_city > 0
                ? <span className="warn">City 누락 {stats.places_missing_city}</span>
                : <span className="active">모두 매핑됨</span>}
            </div>
          </Link>

          <Link to="/admin/settings" className="admin-stat-card">
            <div className="admin-stat-label">설정</div>
            <div className="admin-stat-value admin-stat-value-sm">시스템 파라미터</div>
            <div className="admin-stat-detail">
              <span className="muted">LLM · 클러스터링 · Place 매칭</span>
            </div>
          </Link>
        </div>
      )}
    </AdminLayout>
  );
}
