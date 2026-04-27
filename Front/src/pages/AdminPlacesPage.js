import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { apiClient } from '../services/apiClient';
import AdminLayout from '../components/AdminLayout';
import '../styles/AdminUsersPage.css';
import '../styles/AdminPlacesPage.css';

const PAGE_SIZE = 20;

export default function AdminPlacesPage({ toggleTheme, theme }) {
  const { isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [missingCity, setMissingCity] = useState(false);
  const [sort, setSort] = useState('recent');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [actionId, setActionId] = useState(null);

  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadPlaces = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        page: String(page),
        size: String(PAGE_SIZE),
        sort,
      });
      if (search.trim()) params.append('q', search.trim());
      if (missingCity) params.append('missing_city', 'true');

      const data = await apiClient.get(`/api/v1/admin/places?${params.toString()}`);
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (err) {
      if (err?.status === 403) setError('관리자 권한이 없습니다.');
      else setError(err?.message || 'Place 목록을 불러오는데 실패했습니다.');
    } finally {
      setLoading(false);
    }
  }, [page, search, missingCity, sort]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate('/');
      return;
    }
    if (isAuthenticated) loadPlaces();
  }, [isAuthenticated, isLoading, navigate, loadPlaces]);

  const handleSearch = (e) => {
    e.preventDefault();
    setPage(1);
    loadPlaces();
  };

  const startEdit = (place) => {
    setEditingId(place.id);
    setEditForm({
      name: place.name || '',
      city: place.city || '',
      country: place.country || '',
      region: place.region || '',
      place_type: place.place_type || '',
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditForm({});
  };

  const saveEdit = async (placeId) => {
    setActionId(placeId);
    try {
      await apiClient.patch(`/api/v1/admin/places/${placeId}`, editForm);
      setEditingId(null);
      setEditForm({});
      await loadPlaces();
    } catch (err) {
      setError(err?.message || '저장 실패');
    } finally {
      setActionId(null);
    }
  };

  const regeocode = async (place) => {
    if (!window.confirm(`"${place.name}" 위치 재지오코딩? Google API 호출됩니다.`)) return;
    setActionId(place.id);
    try {
      await apiClient.post(`/api/v1/admin/places/${place.id}/regeocode`);
      await loadPlaces();
    } catch (err) {
      setError(err?.message || '재지오코딩 실패');
    } finally {
      setActionId(null);
    }
  };

  const deletePlace = async (place) => {
    if (!window.confirm(`"${place.name}" Place를 삭제하시겠습니까?\n참조하는 RouteStop이 있으면 차단됩니다.`)) return;
    setActionId(place.id);
    try {
      await apiClient.delete(`/api/v1/admin/places/${place.id}`);
      await loadPlaces();
    } catch (err) {
      setError(err?.message || '삭제 실패');
    } finally {
      setActionId(null);
    }
  };

  if (isLoading) return <div className="admin-loading">로딩 중...</div>;

  return (
    <AdminLayout
      toggleTheme={toggleTheme}
      theme={theme}
      title="Place 관리"
      subtitle="잘못 매핑된 장소 보정, 재지오코딩, 삭제. 도시명이 비어있는 케이스를 우선 정리하세요."
    >
      <div className="admin-users-inner">
        <form className="admin-users-toolbar" onSubmit={handleSearch}>
          <input
            type="text"
            placeholder="이름/주소 검색"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="admin-text-input"
          />
          <select
            value={sort}
            onChange={(e) => { setSort(e.target.value); setPage(1); }}
            className="admin-select-input"
          >
            <option value="recent">최근 등록</option>
            <option value="visits">방문순</option>
          </select>
          <label className="admin-checkbox-label">
            <input
              type="checkbox"
              checked={missingCity}
              onChange={(e) => { setMissingCity(e.target.checked); setPage(1); }}
            />
            City 없음만
          </label>
          <button type="submit" className="admin-search-btn">검색</button>
        </form>

        {error && <div className="admin-error">{error}</div>}

        <div className="admin-users-table-wrapper">
          <table className="admin-users-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>이름</th>
                <th>위치</th>
                <th>좌표</th>
                <th>방문</th>
                <th>액션</th>
              </tr>
            </thead>
            <tbody>
              {loading && <tr><td colSpan="6" className="admin-users-empty">불러오는 중...</td></tr>}
              {!loading && items.length === 0 && (
                <tr><td colSpan="6" className="admin-users-empty">Place가 없습니다.</td></tr>
              )}
              {!loading && items.map((p) => (
                <React.Fragment key={p.id}>
                  <tr>
                    <td>{p.id}</td>
                    <td>
                      <div className="admin-place-name">{p.name}</div>
                      {p.place_type && <div className="admin-user-name">{p.place_type}</div>}
                    </td>
                    <td>
                      {(!p.city || !p.country) && <span className="admin-deleted-tag">불완전</span>}
                      <div>{p.country || '-'} / {p.city || '-'}</div>
                      {p.region && <div className="admin-user-name">{p.region}</div>}
                    </td>
                    <td className="admin-place-coords">
                      {p.latitude.toFixed(4)},<br />{p.longitude.toFixed(4)}
                    </td>
                    <td className="admin-users-num">{p.visit_count}</td>
                    <td className="admin-post-actions">
                      <button
                        className="admin-action-btn primary"
                        onClick={() => startEdit(p)}
                        disabled={actionId === p.id || editingId === p.id}
                      >보정</button>
                      <button
                        className="admin-action-btn"
                        onClick={() => regeocode(p)}
                        disabled={actionId === p.id}
                      >재지오</button>
                      <button
                        className="admin-action-btn danger"
                        onClick={() => deletePlace(p)}
                        disabled={actionId === p.id}
                      >삭제</button>
                    </td>
                  </tr>
                  {editingId === p.id && (
                    <tr className="admin-place-edit-row">
                      <td colSpan="6">
                        <div className="admin-place-edit-form">
                          <div className="admin-place-edit-grid">
                            <label>
                              이름
                              <input
                                type="text"
                                value={editForm.name}
                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                className="admin-text-input"
                              />
                            </label>
                            <label>
                              국가
                              <input
                                type="text"
                                value={editForm.country}
                                onChange={(e) => setEditForm({ ...editForm, country: e.target.value })}
                                className="admin-text-input"
                              />
                            </label>
                            <label>
                              도시
                              <input
                                type="text"
                                value={editForm.city}
                                onChange={(e) => setEditForm({ ...editForm, city: e.target.value })}
                                className="admin-text-input"
                              />
                            </label>
                            <label>
                              지역(region)
                              <input
                                type="text"
                                value={editForm.region}
                                onChange={(e) => setEditForm({ ...editForm, region: e.target.value })}
                                className="admin-text-input"
                              />
                            </label>
                            <label>
                              유형(place_type)
                              <input
                                type="text"
                                value={editForm.place_type}
                                onChange={(e) => setEditForm({ ...editForm, place_type: e.target.value })}
                                className="admin-text-input"
                              />
                            </label>
                          </div>
                          <div className="admin-place-edit-actions">
                            <button
                              className="admin-action-btn primary"
                              onClick={() => saveEdit(p.id)}
                              disabled={actionId === p.id}
                            >저장</button>
                            <button
                              className="admin-action-btn"
                              onClick={cancelEdit}
                              disabled={actionId === p.id}
                            >취소</button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
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
