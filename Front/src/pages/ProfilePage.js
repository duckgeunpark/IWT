import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import { apiClient } from '../services/apiClient';
import { formatDate } from '../utils/dateUtils';
import useDisplayName from '../hooks/useDisplayName';
import '../styles/ProfilePage.css';

const GRADIENTS = [
  'linear-gradient(135deg,#667eea,#764ba2)',
  'linear-gradient(135deg,#f093fb,#f5576c)',
  'linear-gradient(135deg,#4facfe,#00f2fe)',
  'linear-gradient(135deg,#43e97b,#38f9d7)',
  'linear-gradient(135deg,#fa709a,#fee140)',
  'linear-gradient(135deg,#a18cd1,#fbc2eb)',
];

// ── 여행 카드 (프로필용) ──
const ProfileTripCard = ({ trip, index, onDelete, onClick }) => {
  const gradient = GRADIENTS[index % GRADIENTS.length];
  const [hovered, setHovered] = useState(false);

  return (
    <div
      className="prof-trip-card"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
    >
      <div className="prof-trip-thumb" style={{ background: gradient }}>
        {trip.thumbnail_url ? (
          <img src={trip.thumbnail_url} alt={trip.title} className="prof-trip-img" />
        ) : (
          <span className="prof-trip-icon">✈️</span>
        )}
        {trip.photo_count > 0 && (
          <span className="prof-trip-count">📷 {trip.photo_count}</span>
        )}
        {hovered && (
          <button
            className="prof-trip-delete-btn"
            onClick={(e) => { e.stopPropagation(); onDelete(trip); }}
            title="삭제"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
              <path d="M9 6V4h6v2" />
            </svg>
          </button>
        )}
      </div>
      <div className="prof-trip-body">
        <p className="prof-trip-title">{trip.title}</p>
        <p className="prof-trip-meta">
          {trip.created_at ? formatDate(trip.created_at) : ''}
          {trip.photo_count > 0 ? ` · ${trip.photo_count}장` : ''}
        </p>
      </div>
    </div>
  );
};

// ── 저장된 여행 카드 ──
const SavedTripCard = ({ trip, index, onClick }) => {
  const gradient = GRADIENTS[index % GRADIENTS.length];
  return (
    <div className="prof-trip-card" onClick={onClick}>
      <div className="prof-trip-thumb" style={{ background: gradient }}>
        {trip.thumbnail_url ? (
          <img src={trip.thumbnail_url} alt={trip.title} className="prof-trip-img" />
        ) : (
          <span className="prof-trip-icon">✈️</span>
        )}
        {trip.photo_count > 0 && (
          <span className="prof-trip-count">📷 {trip.photo_count}</span>
        )}
      </div>
      <div className="prof-trip-body">
        <p className="prof-trip-title">{trip.title}</p>
        <p className="prof-trip-meta">
          {trip.author?.name && <span>{trip.author.name} · </span>}
          {trip.created_at ? formatDate(trip.created_at) : ''}
        </p>
      </div>
    </div>
  );
};

// ── 프로필 페이지 ──
const ProfilePage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const { isAuthenticated, user, isLoading, loginWithRedirect, getAccessTokenSilently } = useAuth0();
  const [activeTab, setActiveTab] = useState('trips');
  const [myTrips, setMyTrips] = useState([]);
  const [savedTrips, setSavedTrips] = useState([]);
  const [followers, setFollowers] = useState([]);
  const [following, setFollowing] = useState([]);
  const [showUserList, setShowUserList] = useState(null);
  const [dataLoading, setDataLoading] = useState(true);

  // 편집 모달
  const [showEditModal, setShowEditModal] = useState(false);
  const [editName, setEditName] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [dbPicture, setDbPicture] = useState(null);

  const displayName = useDisplayName();

  // 삭제 확인 모달
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // 여행 패턴 분석
  const [travelPattern, setTravelPattern] = useState(null);
  const [patternLoading, setPatternLoading] = useState(false);

  const loadProfileData = useCallback(async () => {
    if (!isAuthenticated || !user?.sub) return;
    setDataLoading(true);
    try {
      const [meRes, postsRes, bookmarksRes, followersRes, followingRes] = await Promise.allSettled([
        apiClient.get('/api/v1/users/me'),
        apiClient.get(`/api/v1/posts/user/${encodeURIComponent(user.sub)}?skip=0&limit=50`),
        apiClient.get('/api/v1/posts/bookmarked?limit=50'),
        apiClient.get(`/api/v1/users/${encodeURIComponent(user.sub)}/followers?limit=100`),
        apiClient.get(`/api/v1/users/${encodeURIComponent(user.sub)}/following?limit=100`),
      ]);

      // DB에서 읽어온 이름/사진 (Auth0 캐시 우회)
      if (meRes.status === 'fulfilled' && meRes.value) {
        if (meRes.value.picture) setDbPicture(meRes.value.picture);
      }
      if (postsRes.status === 'fulfilled') setMyTrips(postsRes.value.posts || []);
      if (bookmarksRes.status === 'fulfilled') setSavedTrips(bookmarksRes.value.posts || []);
      if (followersRes.status === 'fulfilled') setFollowers(followersRes.value.users || []);
      if (followingRes.status === 'fulfilled') setFollowing(followingRes.value.users || []);
    } catch (err) {
      console.error('프로필 데이터 로드 실패:', err);
    } finally {
      setDataLoading(false);
    }
  }, [isAuthenticated, user?.sub]);

  useEffect(() => { loadProfileData(); }, [loadProfileData]);

  // 삭제 처리
  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      await apiClient.delete(`/api/v1/posts/${deleteTarget.id}`);
      setMyTrips(prev => prev.filter(t => t.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (err) {
      console.error('삭제 실패:', err);
      alert('삭제에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setDeleteLoading(false);
    }
  }, [deleteTarget]);

  // 프로필 편집 저장
  const handleEditSave = useCallback(async () => {
    if (!user?.sub || !editName.trim()) return;
    setEditSaving(true);
    try {
      await apiClient.put(`/api/v1/users/profile/${encodeURIComponent(user.sub)}`, {
        name: editName.trim(),
      });
      setShowEditModal(false);
    } catch (err) {
      console.error('프로필 업데이트 실패:', err);
      alert('프로필 업데이트에 실패했습니다.');
    } finally {
      setEditSaving(false);
    }
  }, [user?.sub, editName]);

  const openEditModal = () => {
    setEditName(displayName !== '사용자' ? displayName : '');
    setShowEditModal(true);
  };
  const avatarSrc = dbPicture || user?.picture || null;

  const stats = {
    posts: myTrips.length,
    followers: followers.length,
    following: following.length,
  };

  if (isLoading) {
    return (
      <div className="profile-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="profile-loading">
          <div className="page-loading-spinner" />
          <p>프로필을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="profile-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="profile-login-prompt">
          <div className="prompt-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <h2>로그인이 필요합니다</h2>
          <p>프로필을 확인하려면 로그인해주세요.</p>
          <button className="prompt-login-btn" onClick={() => loginWithRedirect()}>로그인</button>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="profile-content">
        {/* ── 프로필 헤더 ── */}
        <div className="profile-header">
          <div className="profile-avatar-section">
            <div className="profile-avatar-ring">
              {avatarSrc ? (
                <img src={avatarSrc} alt="프로필" className="profile-avatar-img" />
              ) : (
                <div className="profile-avatar-default">
                  {displayName[0]?.toUpperCase() || '?'}
                </div>
              )}
            </div>
          </div>

          <div className="profile-info-section">
            <div className="profile-name-row">
              <h1 className="profile-username">{displayName}</h1>
              <button className="profile-edit-btn" onClick={openEditModal}>프로필 편집</button>
            </div>

            <div className="profile-stats-row">
              <div className="profile-stat">
                <strong>{stats.posts}</strong>
                <span>게시물</span>
              </div>
              <div className="profile-stat clickable" onClick={() => setShowUserList('followers')}>
                <strong>{stats.followers}</strong>
                <span>팔로워</span>
              </div>
              <div className="profile-stat clickable" onClick={() => setShowUserList('following')}>
                <strong>{stats.following}</strong>
                <span>팔로잉</span>
              </div>
            </div>

            <div className="profile-bio">
              {user?.email && <span className="profile-email">{user.email}</span>}
            </div>
          </div>
        </div>

        {/* ── 탭 ── */}
        <div className="profile-tabs">
          <button
            className={`profile-tab ${activeTab === 'trips' ? 'active' : ''}`}
            onClick={() => setActiveTab('trips')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
            </svg>
            내 여행
          </button>
          <button
            className={`profile-tab ${activeTab === 'saved' ? 'active' : ''}`}
            onClick={() => setActiveTab('saved')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
            </svg>
            저장됨
          </button>
          <button
            className={`profile-tab ${activeTab === 'pattern' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('pattern');
              if (!travelPattern && !patternLoading && user?.sub) {
                setPatternLoading(true);
                apiClient.get(`/api/v1/users/${encodeURIComponent(user.sub)}/travel-pattern`)
                  .then(res => setTravelPattern(res?.pattern || null))
                  .catch(() => setTravelPattern(null))
                  .finally(() => setPatternLoading(false));
              }
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            여행 패턴
          </button>
        </div>

        {/* ── 콘텐츠 ── */}
        <div className="profile-grid">
          {dataLoading ? (
            <div className="profile-loading-inline">
              <div className="page-loading-spinner" />
            </div>
          ) : activeTab === 'trips' ? (
            myTrips.length === 0 ? (
              <div className="profile-empty">
                <p>아직 여행 기록이 없어요.</p>
                <button className="explore-link-btn" onClick={() => navigate('/trip/new')}>
                  새 여행 만들기
                </button>
              </div>
            ) : (
              myTrips.map((trip, i) => (
                <ProfileTripCard
                  key={trip.id}
                  trip={trip}
                  index={i}
                  onDelete={setDeleteTarget}
                  onClick={() => navigate(`/trip/${trip.id}`)}
                />
              ))
            )
          ) : activeTab === 'saved' ? (
            savedTrips.length === 0 ? (
              <div className="profile-empty">
                <p>저장한 여행이 없습니다.</p>
                <button className="explore-link-btn" onClick={() => navigate('/explore')}>
                  여행 탐색하기
                </button>
              </div>
            ) : (
              savedTrips.map((trip, i) => (
                <SavedTripCard
                  key={trip.id}
                  trip={trip}
                  index={i}
                  onClick={() => navigate(`/trip/${trip.id}`)}
                />
              ))
            )
          ) : null}

          {/* 여행 패턴 탭 (grid 밖) */}
        </div>

        {activeTab === 'pattern' && (
          <div className="travel-pattern-section">
            {patternLoading ? (
              <div className="pattern-loading">
                <div className="page-loading-spinner" />
                <p>AI가 여행 패턴을 분석하는 중...</p>
              </div>
            ) : !travelPattern ? (
              <div className="profile-empty">
                <p>여행 기록이 충분하지 않아 패턴을 분석할 수 없습니다.</p>
              </div>
            ) : (
              <div className="pattern-content">
                {/* 요약 카드 */}
                {travelPattern.summary && (
                  <div className="pattern-summary-card">
                    <h4 className="pattern-summary-title">✈️ 나의 여행 스타일</h4>
                    <p className="pattern-summary-text">{travelPattern.summary}</p>
                    {travelPattern.insight && (
                      <p className="pattern-insight-text">{travelPattern.insight}</p>
                    )}
                    {travelPattern.recommendation && (
                      <p className="pattern-recommend-text">💡 다음 여행 추천: {travelPattern.recommendation}</p>
                    )}
                  </div>
                )}

                {/* 통계 그리드 */}
                <div className="pattern-stats-grid">
                  <div className="pattern-stat-card">
                    <p className="pattern-stat-value">{travelPattern.total_trips}</p>
                    <p className="pattern-stat-label">총 여행</p>
                  </div>
                  {travelPattern.peak_months?.length > 0 && (
                    <div className="pattern-stat-card">
                      <p className="pattern-stat-value">{travelPattern.peak_months.join(' · ')}</p>
                      <p className="pattern-stat-label">선호 여행 시기</p>
                    </div>
                  )}
                </div>

                {/* 자주 방문한 나라 */}
                {travelPattern.top_countries?.length > 0 && (
                  <div className="pattern-list-section">
                    <h5 className="pattern-list-title">🌍 자주 방문한 나라</h5>
                    <div className="pattern-bar-list">
                      {travelPattern.top_countries.map((item, i) => (
                        <div key={item.name} className="pattern-bar-item">
                          <span className="pattern-bar-label">{item.name}</span>
                          <div className="pattern-bar-track">
                            <div
                              className="pattern-bar-fill"
                              style={{ width: `${(item.count / travelPattern.top_countries[0].count) * 100}%` }}
                            />
                          </div>
                          <span className="pattern-bar-count">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 자주 방문한 도시 */}
                {travelPattern.top_cities?.length > 0 && (
                  <div className="pattern-list-section">
                    <h5 className="pattern-list-title">🏙️ 자주 방문한 도시</h5>
                    <div className="pattern-bar-list">
                      {travelPattern.top_cities.map((item) => (
                        <div key={item.name} className="pattern-bar-item">
                          <span className="pattern-bar-label">{item.name}</span>
                          <div className="pattern-bar-track">
                            <div
                              className="pattern-bar-fill"
                              style={{ width: `${(item.count / travelPattern.top_cities[0].count) * 100}%` }}
                            />
                          </div>
                          <span className="pattern-bar-count">{item.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 주요 태그 */}
                {travelPattern.top_tags?.length > 0 && (
                  <div className="pattern-list-section">
                    <h5 className="pattern-list-title">🏷️ 나의 여행 키워드</h5>
                    <div className="pattern-tag-cloud">
                      {travelPattern.top_tags.map((item) => (
                        <span key={item.tag} className="pattern-tag-chip">
                          #{item.tag}
                          <span className="pattern-tag-count">{item.count}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 팔로워/팔로잉 모달 ── */}
      {showUserList && (
        <div className="user-list-overlay" onClick={() => setShowUserList(null)}>
          <div className="user-list-modal" onClick={(e) => e.stopPropagation()}>
            <div className="user-list-header">
              <h3>{showUserList === 'followers' ? '팔로워' : '팔로잉'}</h3>
              <button className="user-list-close" onClick={() => setShowUserList(null)}>&times;</button>
            </div>
            <div className="user-list-body">
              {(showUserList === 'followers' ? followers : following).length === 0 ? (
                <p className="user-list-empty">
                  {showUserList === 'followers' ? '아직 팔로워가 없습니다.' : '아직 팔로우하는 사람이 없습니다.'}
                </p>
              ) : (
                (showUserList === 'followers' ? followers : following).map((u) => (
                  <div
                    key={u.id}
                    className="user-list-item"
                    style={{ cursor: 'pointer' }}
                    onClick={() => { setShowUserList(null); navigate(`/profile/${encodeURIComponent(u.id)}`); }}
                  >
                    <div className="user-list-avatar">
                      {u.picture ? (
                        <img src={u.picture} alt="" />
                      ) : (
                        <div className="user-list-avatar-default">
                          {(u.name || u.id || '?')[0].toUpperCase()}
                        </div>
                      )}
                    </div>
                    <div className="user-list-info">
                      <span className="user-list-name">{u.name || u.id}</span>
                      <span className="user-list-meta">
                        게시물 {u.posts_count || 0} &middot; 팔로워 {u.followers_count || 0}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── 프로필 편집 모달 ── */}
      {showEditModal && (
        <div className="prof-modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="prof-edit-modal" onClick={(e) => e.stopPropagation()}>
            <div className="prof-modal-header">
              <h3>프로필 편집</h3>
              <button className="prof-modal-close" onClick={() => setShowEditModal(false)}>&times;</button>
            </div>
            <div className="prof-modal-body">
              <div className="prof-field">
                <label className="prof-field-label">이메일</label>
                <div className="prof-field-readonly">{user?.email || '-'}</div>
              </div>
              <div className="prof-field">
                <label className="prof-field-label">표시 이름</label>
                <input
                  className="prof-field-input"
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="다른 사용자에게 보여질 이름"
                  maxLength={40}
                />
              </div>
            </div>
            <div className="prof-modal-footer">
              <button className="prof-cancel-btn" onClick={() => setShowEditModal(false)}>취소</button>
              <button
                className="prof-save-btn"
                onClick={handleEditSave}
                disabled={editSaving || !editName.trim()}
              >
                {editSaving ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 삭제 확인 모달 ── */}
      {deleteTarget && (
        <div className="prof-modal-overlay" onClick={() => setDeleteTarget(null)}>
          <div className="prof-delete-modal" onClick={(e) => e.stopPropagation()}>
            <div className="prof-modal-header">
              <h3>여행 삭제</h3>
              <button className="prof-modal-close" onClick={() => setDeleteTarget(null)}>&times;</button>
            </div>
            <div className="prof-delete-body">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="1.5">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <p className="prof-delete-title">정말 삭제할까요?</p>
              <p className="prof-delete-desc">
                <strong>"{deleteTarget.title}"</strong>을(를) 삭제하면 복구할 수 없습니다.
              </p>
            </div>
            <div className="prof-modal-footer">
              <button className="prof-cancel-btn" onClick={() => setDeleteTarget(null)}>취소</button>
              <button
                className="prof-delete-confirm-btn"
                onClick={handleDeleteConfirm}
                disabled={deleteLoading}
              >
                {deleteLoading ? '삭제 중...' : '삭제'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProfilePage;
