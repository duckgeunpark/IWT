import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import TravelCard from '../components/TravelCard';
import { apiClient } from '../services/apiClient';
import '../styles/ProfilePage.css';

const ProfilePage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const { isAuthenticated, user, isLoading, loginWithRedirect } = useAuth0();
  const [activeTab, setActiveTab] = useState('trips');
  const [myTrips, setMyTrips] = useState([]);
  const [savedTrips, setSavedTrips] = useState([]);
  const [followers, setFollowers] = useState([]);
  const [following, setFollowing] = useState([]);
  const [showUserList, setShowUserList] = useState(null); // 'followers' | 'following' | null
  const [dataLoading, setDataLoading] = useState(true);

  const loadProfileData = useCallback(async () => {
    if (!isAuthenticated || !user?.sub) return;
    setDataLoading(true);
    try {
      const [postsRes, bookmarksRes, followersRes, followingRes] = await Promise.allSettled([
        apiClient.get(`/api/v1/search/posts?user_id=${encodeURIComponent(user.sub)}&limit=50`),
        apiClient.get('/api/v1/posts/bookmarked?limit=50'),
        apiClient.get(`/api/v1/users/${encodeURIComponent(user.sub)}/followers?limit=100`),
        apiClient.get(`/api/v1/users/${encodeURIComponent(user.sub)}/following?limit=100`),
      ]);

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

  useEffect(() => {
    loadProfileData();
  }, [loadProfileData]);

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
          <button className="prompt-login-btn" onClick={() => loginWithRedirect()}>
            로그인
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="profile-content">
        {/* Profile Header (Instagram Style) */}
        <div className="profile-header">
          <div className="profile-avatar-section">
            <div className="profile-avatar-ring">
              {user?.picture ? (
                <img src={user.picture} alt="프로필" className="profile-avatar-img" />
              ) : (
                <div className="profile-avatar-default">
                  {(user?.name || user?.email || '?')[0].toUpperCase()}
                </div>
              )}
            </div>
          </div>

          <div className="profile-info-section">
            <div className="profile-name-row">
              <h1 className="profile-username">{user?.nickname || user?.name || user?.email}</h1>
              <button className="profile-edit-btn" onClick={() => {}}>프로필 편집</button>
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

            {user?.name && (
              <div className="profile-bio">
                <span className="profile-display-name">{user.name}</span>
                {user?.email && <span className="profile-email">{user.email}</span>}
              </div>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="profile-tabs">
          <button
            className={`profile-tab ${activeTab === 'trips' ? 'active' : ''}`}
            onClick={() => setActiveTab('trips')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
            내 여행
          </button>
          <button
            className={`profile-tab ${activeTab === 'saved' ? 'active' : ''}`}
            onClick={() => setActiveTab('saved')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
            저장됨
          </button>
        </div>

        {/* Content */}
        <div className="profile-grid">
          {dataLoading ? (
            <div className="profile-loading-inline">
              <div className="page-loading-spinner" />
            </div>
          ) : activeTab === 'trips' ? (
            <>
              <TravelCard type="create" onClick={() => navigate('/trip/new')} />
              {myTrips.map((trip) => (
                <TravelCard
                  key={trip.id}
                  date={trip.created_at ? new Date(trip.created_at).toLocaleDateString('ko-KR') : ''}
                  title={trip.title}
                  subtitle={`${trip.photo_count || 0}장`}
                  colorTheme={['blue', 'pink', 'green', 'purple', 'yellow'][trip.id % 5]}
                  photoCount={trip.photo_count}
                  onClick={() => navigate(`/trip/${trip.id}`)}
                />
              ))}
            </>
          ) : (
            <>
              {savedTrips.length === 0 ? (
                <div className="profile-empty">
                  <p>저장한 여행이 없습니다.</p>
                  <button className="explore-link-btn" onClick={() => navigate('/explore')}>
                    여행 경로 탐색하기
                  </button>
                </div>
              ) : (
                savedTrips.map((trip) => (
                  <TravelCard
                    key={trip.id}
                    date={trip.created_at ? new Date(trip.created_at).toLocaleDateString('ko-KR') : ''}
                    title={trip.title}
                    subtitle={`${trip.photo_count || 0}장`}
                    colorTheme={['blue', 'pink', 'green', 'purple', 'yellow'][trip.id % 5]}
                    photoCount={trip.photo_count}
                    onClick={() => navigate(`/trip/${trip.id}`)}
                  />
                ))
              )}
            </>
          )}
        </div>

        {/* Followers / Following Modal */}
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
                    <div key={u.id} className="user-list-item">
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
    </div>
  );
};

export default ProfilePage;
