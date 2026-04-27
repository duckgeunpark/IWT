import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';
import AdminLayout from '../components/AdminLayout';
import '../styles/AdminUsersPage.css';

const PAGE_SIZE = 20;

export default function AdminUsersPage({ toggleTheme, theme }) {
  const { isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState('all'); // all | active | inactive
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionUserId, setActionUserId] = useState(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ page: String(page), size: String(PAGE_SIZE) });
      if (search.trim()) params.append('q', search.trim());
      if (activeFilter === 'active') params.append('active', 'true');
      if (activeFilter === 'inactive') params.append('active', 'false');

      const data = await apiClient.get(`/api/v1/admin/users?${params.toString()}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      if (err?.status === 403) {
        setError('관리자 권한이 없습니다.');
      } else {
        setError(err?.message || '사용자 목록을 불러오는데 실패했습니다.');
      }
    } finally {
      setLoading(false);
    }
  }, [page, search, activeFilter]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/');
      return;
    }
    if (isAuthenticated) {
      loadUsers();
    }
  }, [isAuthenticated, isLoading, navigate, loadUsers]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadUsers();
  };

  const toggleActive = async (user) => {
    const next = !user.is_active;
    const action = next ? '활성화' : '비활성화';
    if (!window.confirm(`${user.email} 계정을 ${action}하시겠습니까?`)) return;

    setActionUserId(user.id);
    try {
      await apiClient.patch(`/api/v1/admin/users/${encodeURIComponent(user.id)}`, { is_active: next });
      await loadUsers();
    } catch (err) {
      setError(err?.message || `${action} 실패`);
    } finally {
      setActionUserId(null);
    }
  };

  if (isLoading) return <div className="admin-loading">로딩 중...</div>;

  return (
    <AdminLayout
      toggleTheme={toggleTheme}
      theme={theme}
      title="사용자 관리"
      subtitle="사용자 계정 활성/비활성 관리. 비활성화 시 로그인 및 활동이 차단됩니다."
    >
      <div className="admin-users-inner">
        <form className="admin-users-toolbar" onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="이메일 또는 이름 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="admin-text-input"
          />
          <select
            value={activeFilter}
            onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}
            className="admin-select-input"
          >
            <option value="all">전체</option>
            <option value="active">활성</option>
            <option value="inactive">비활성</option>
          </select>
          <button type="submit" className="admin-search-btn">검색</button>
        </form>

        {error && <div className="admin-error">{error}</div>}

        <div className="admin-users-table-wrapper">
          <table className="admin-users-table">
            <thead>
              <tr>
                <th>프로필</th>
                <th>이메일 / 이름</th>
                <th>가입일</th>
                <th>게시글</th>
                <th>상태</th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan="6" className="admin-users-empty">불러오는 중...</td></tr>
              )}
              {!loading && items.length === 0 && (
                <tr><td colSpan="6" className="admin-users-empty">사용자가 없습니다.</td></tr>
              )}
              {!loading && items.map((u) => (
                <tr key={u.id}>
                  <td>
                    {u.picture
                      ? <img src={u.picture} alt="" className="admin-user-avatar" />
                      : <div className="admin-user-avatar admin-user-avatar-placeholder">{(u.name || u.email || '?')[0]}</div>
                    }
                  </td>
                  <td>
                    <div className="admin-user-email">{u.email}</div>
                    {u.name && <div className="admin-user-name">{u.name}</div>}
                  </td>
                  <td>{u.created_at ? new Date(u.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                  <td className="admin-users-num">{u.post_count}</td>
                  <td>
                    <span className={`admin-status-badge ${u.is_active ? 'active' : 'inactive'}`}>
                      {u.is_active ? '활성' : '비활성'}
                    </span>
                  </td>
                  <td>
                    <button
                      className={`admin-action-btn ${u.is_active ? 'danger' : 'primary'}`}
                      onClick={() => toggleActive(u)}
                      disabled={actionUserId === u.id}
                    >
                      {actionUserId === u.id ? '처리 중...' : u.is_active ? '비활성화' : '활성화'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="admin-users-pagination">
          <span>총 {total}명 / {page} / {totalPages} 페이지</span>
          <div className="admin-users-pagination-buttons">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loading}
              className="admin-page-btn"
            >이전</button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loading}
              className="admin-page-btn"
            >다음</button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
