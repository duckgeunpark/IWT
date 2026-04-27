import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';
import AdminLayout from '../components/AdminLayout';
import '../styles/AdminUsersPage.css';

const PAGE_SIZE = 20;

export default function AdminPostsPage({ toggleTheme, theme }) {
  const { isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [deletedView, setDeletedView] = useState('exclude'); // exclude | include | only
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionId, setActionId] = useState(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadPosts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ page: String(page), size: String(PAGE_SIZE) });
      if (search.trim()) params.append('q', search.trim());
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (deletedView === 'include') params.append('include_deleted', 'true');
      if (deletedView === 'only') params.append('only_deleted', 'true');

      const data = await apiClient.get(`/api/v1/admin/posts?${params.toString()}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      if (err?.status === 403) setError('관리자 권한이 없습니다.');
      else setError(err?.message || '게시글 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, deletedView]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/');
      return;
    }
    if (isAuthenticated) loadPosts();
  }, [isAuthenticated, isLoading, navigate, loadPosts]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadPosts();
  };

  const softDelete = async (post) => {
    if (!window.confirm(`"${post.title}" 게시글을 삭제하시겠습니까?\n(나중에 복구 가능)`)) return;
    setActionId(post.id);
    try {
      await apiClient.delete(`/api/v1/admin/posts/${post.id}`);
      await loadPosts();
    } catch (err) {
      setError(err?.message || '삭제 실패');
    } finally {
      setActionId(null);
    }
  };

  const restorePost = async (post) => {
    setActionId(post.id);
    try {
      await apiClient.post(`/api/v1/admin/posts/${post.id}/restore`);
      await loadPosts();
    } catch (err) {
      setError(err?.message || '복구 실패');
    } finally {
      setActionId(null);
    }
  };

  const changeStatus = async (post, nextStatus) => {
    setActionId(post.id);
    try {
      await apiClient.patch(`/api/v1/admin/posts/${post.id}`, { status: nextStatus });
      await loadPosts();
    } catch (err) {
      setError(err?.message || '상태 변경 실패');
    } finally {
      setActionId(null);
    }
  };

  if (isLoading) return <div className="admin-loading">로딩 중...</div>;

  return (
    <AdminLayout
      toggleTheme={toggleTheme}
      theme={theme}
      title="게시글 관리"
      subtitle="게시글 검토, 강제 비공개, 소프트 삭제/복구."
    >
      <div className="admin-users-inner">
        <form className="admin-users-toolbar" onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="제목 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="admin-text-input"
          />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="admin-select-input"
          >
            <option value="all">전체 상태</option>
            <option value="published">공개</option>
            <option value="draft">초안</option>
            <option value="private">비공개</option>
          </select>
          <select
            value={deletedView}
            onChange={(e) => { setDeletedView(e.target.value); setPage(1); }}
            className="admin-select-input"
          >
            <option value="exclude">활성만</option>
            <option value="include">삭제 포함</option>
            <option value="only">삭제만</option>
          </select>
          <button type="submit" className="admin-search-btn">검색</button>
        </form>

        {error && <div className="admin-error">{error}</div>}

        <div className="admin-users-table-wrapper">
          <table className="admin-users-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>제목</th>
                <th>작성자</th>
                <th>상태</th>
                <th>작성일</th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan="6" className="admin-users-empty">불러오는 중...</td></tr>}
              {!loading && items.length === 0 && (
                <tr><td colSpan="6" className="admin-users-empty">게시글이 없습니다.</td></tr>
              )}
              {!loading && items.map((p) => (
                <tr key={p.id}>
                  <td>{p.id}</td>
                  <td>
                    <Link to={`/trip/${p.id}`} target="_blank" rel="noopener noreferrer" className="admin-post-title-link">
                      {p.title || '(제목 없음)'}
                    </Link>
                    {p.deleted_at && <span className="admin-deleted-tag">삭제됨</span>}
                  </td>
                  <td>
                    <div className="admin-user-email">{p.author?.email || p.user_id}</div>
                    {p.author?.name && <div className="admin-user-name">{p.author.name}</div>}
                  </td>
                  <td>
                    <span className={`admin-status-badge ${p.status === 'published' ? 'active' : 'inactive'}`}>
                      {p.status}
                    </span>
                  </td>
                  <td>{p.created_at ? new Date(p.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                  <td className="admin-post-actions">
                    {!p.deleted_at && p.status === 'published' && (
                      <button
                        className="admin-action-btn"
                        onClick={() => changeStatus(p, 'private')}
                        disabled={actionId === p.id}
                      >비공개</button>
                    )}
                    {!p.deleted_at && p.status !== 'published' && (
                      <button
                        className="admin-action-btn primary"
                        onClick={() => changeStatus(p, 'published')}
                        disabled={actionId === p.id}
                      >공개</button>
                    )}
                    {!p.deleted_at && (
                      <button
                        className="admin-action-btn danger"
                        onClick={() => softDelete(p)}
                        disabled={actionId === p.id}
                      >삭제</button>
                    )}
                    {p.deleted_at && (
                      <button
                        className="admin-action-btn primary"
                        onClick={() => restorePost(p)}
                        disabled={actionId === p.id}
                      >복구</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="admin-users-pagination">
          <span>총 {total}건 / {page} / {totalPages} 페이지</span>
          <div className="admin-users-pagination-buttons">
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1 || loading} className="admin-page-btn">이전</button>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages || loading} className="admin-page-btn">다음</button>
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}
