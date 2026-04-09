import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import { apiClient } from '../services/apiClient';
import { formatDate } from '../utils/dateUtils';
import '../styles/ProfilePage.css';

const GRADIENTS = [
  'linear-gradient(135deg,#667eea,#764ba2)',
  'linear-gradient(135deg,#f093fb,#f5576c)',
  'linear-gradient(135deg,#4facfe,#00f2fe)',
  'linear-gradient(135deg,#43e97b,#38f9d7)',
  'linear-gradient(135deg,#fa709a,#fee140)',
  'linear-gradient(135deg,#a18cd1,#fbc2eb)',
];

const UserProfilePage = ({ toggleTheme, theme }) => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth0();

  const [profile, setProfile] = useState(null);
  const [posts, setPosts] = useState([]);
  const [followers, setFollowers] = useState([]);
  const [following, setFollowing] = useState([]);
  const [loading, setLoading] = useState(true);
  const [followLoading, setFollowLoading] = useState(false);
  const [showUserList, setShowUserList] = useState(null);

  // 내 프로필이면 /profile로 리다이렉트
  useEffect(() => {
    if (isAuthenticated && user?.sub && userId === user.sub) {
      navigate('/profile', { replace: true });
    }
  }, [isAuthenticated, user?.sub, userId, navigate]);

  const loadData = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const [profileRes, postsRes] = await Promise.allSettled([
        apiClient.get(`/api/v1/users/${encodeURIComponent(userId)}/profile`),
        apiClient.get(`/api/v1/posts/user/${encodeURIComponent(userId)}?skip=0&limit=50`),
      ]);
      if (profileRes.status === 'fulfilled') setProfile(profileRes.value);
      if (postsRes.status === 'fulfilled') setPosts(postsRes.value.posts || []);
    } catch (err) {
      console.error('프로필 로드 실패:', err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => { loadData(); }, [loadData]);

  const loadUserList = useCallback(async (type) => {
    if (!userId) return;
    try {
      const res = await apiClient.get(
        `/api/v1/users/${encodeURIComponent(userId)}/${type}?limit=100`
      );
      if (type === 'followers') setFollowers(res.users || []);
      else setFollowing(res.users || []);
    } catch (err) {
      console.error('목록 로드 실패:', err);
    }
  }, [userId]);

  const handleShowUserList = (type) => {
    setShowUserList(type);
    loadUserList(type);
  };

  const handleFollow = useCallback(async () => {
    if (!isAuthenticated) {
      alert('로그인이 필요합니다.');
      return;
    }
    setFollowLoading(true);
    try {
      const res = await apiClient.post(`/api/v1/users/${encodeURIComponent(userId)}/follow`);
      setProfile(prev => ({
        ...prev,
        is_following: res.following,
        followers_count: res.followers_count,
      }));
    } catch (err) {
      console.error('팔로우 실패:', err);
    } finally {
      setFollowLoading(false);
    }
  }, [isAuthenticated, userId]);

  if (loading) {
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

  if (!profile) {
    return (
      <div className="profile-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="profile-loading">
          <p>사용자를 찾을 수 없습니다.</p>
          <button className="explore-link-btn" onClick={() => navigate(-1)}>돌아가기</button>
        </div>
      </div>
    );
  }

  const displayName = profile.name || userId;

  return (
    <div className="profile-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="profile-content">
        {/* ── 프로필 헤더 ── */}
        <div className="profile-header">
          <div className="profile-avatar-section">
            <div className="profile-avatar-ring">
              {profile.picture ? (
                <img src={profile.picture} alt="프로필" className="profile-avatar-img" />
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
              {/* 팔로우 / 언팔로우 버튼 */}
              <button
                className={`profile-follow-btn ${profile.is_following ? 'following' : ''}`}
                onClick={handleFollow}
                disabled={followLoading}
              >
                {profile.is_following ? '언팔로우' : '팔로우'}
              </button>
            </div>

            <div className="profile-stats-row">
              <div className="profile-stat">
                <strong>{profile.posts_count}</strong>
                <span>게시물</span>
              </div>
              <div className="profile-stat clickable" onClick={() => handleShowUserList('followers')}>
                <strong>{profile.followers_count}</strong>
                <span>팔로워</span>
              </div>
              <div className="profile-stat clickable" onClick={() => handleShowUserList('following')}>
                <strong>{profile.following_count}</strong>
                <span>팔로잉</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── 탭 (게시물만) ── */}
        <div className="profile-tabs">
          <button className="profile-tab active">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
            </svg>
            게시물
          </button>
        </div>

        {/* ── 게시물 그리드 ── */}
        <div className="profile-grid">
          {posts.length === 0 ? (
            <div className="profile-empty">
              <p>아직 여행 기록이 없어요.</p>
            </div>
          ) : (
            posts.map((trip, i) => (
              <div
                key={trip.id}
                className="prof-trip-card"
                onClick={() => navigate(`/trip/${trip.id}`)}
              >
                <div
                  className="prof-trip-thumb"
                  style={{ background: GRADIENTS[i % GRADIENTS.length] }}
                >
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
                    {trip.created_at ? formatDate(trip.created_at) : ''}
                    {trip.photo_count > 0 ? ` · ${trip.photo_count}장` : ''}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
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
    </div>
  );
};

export default UserProfilePage;
