import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import TravelCard from '../components/TravelCard';
import '../styles/ProfilePage.css';

const ProfilePage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const { isAuthenticated, user, isLoading, loginWithRedirect } = useAuth0();
  const [activeTab, setActiveTab] = useState('trips');

  // 샘플 데이터 — 나중에 API로 대체
  const myTrips = [
    {
      id: 2,
      date: '25년 05월 02일',
      title: '제주도 맛집 투어',
      subtitle: '1박 2일',
      status: '작성중',
      colorTheme: 'pink',
      photoCount: 34,
      locationCount: 5,
    },
    {
      id: 5,
      date: '24년 12월 25일',
      title: '유럽 크리스마스 마켓 투어',
      subtitle: '5박 6일',
      colorTheme: 'green',
      photoCount: 156,
      locationCount: 9,
    },
  ];

  const savedTrips = [
    {
      id: 1,
      date: '24년 05월 12일',
      title: 'LA에서 시작하는 북미 횡단 여행',
      subtitle: '5박 6일',
      author: 'traveler_kim',
      colorTheme: 'blue',
      photoCount: 127,
      locationCount: 8,
    },
  ];

  const stats = {
    trips: myTrips.length,
    photos: myTrips.reduce((sum, t) => sum + (t.photoCount || 0), 0),
    locations: myTrips.reduce((sum, t) => sum + (t.locationCount || 0), 0),
    saved: savedTrips.length,
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
                <strong>{stats.trips}</strong>
                <span>여행</span>
              </div>
              <div className="profile-stat">
                <strong>{stats.photos}</strong>
                <span>사진</span>
              </div>
              <div className="profile-stat">
                <strong>{stats.locations}</strong>
                <span>장소</span>
              </div>
              <div className="profile-stat">
                <strong>{stats.saved}</strong>
                <span>저장됨</span>
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
          {activeTab === 'trips' && (
            <>
              <TravelCard type="create" onClick={() => navigate('/trip/new')} />
              {myTrips.map((trip) => (
                <TravelCard
                  key={trip.id}
                  date={trip.date}
                  title={trip.title}
                  subtitle={trip.subtitle}
                  status={trip.status}
                  colorTheme={trip.colorTheme}
                  photoCount={trip.photoCount}
                  locationCount={trip.locationCount}
                  onClick={() => navigate(`/trip/${trip.id}`)}
                />
              ))}
            </>
          )}

          {activeTab === 'saved' && (
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
                    date={trip.date}
                    title={trip.title}
                    subtitle={trip.subtitle}
                    author={trip.author}
                    colorTheme={trip.colorTheme}
                    photoCount={trip.photoCount}
                    locationCount={trip.locationCount}
                    onClick={() => navigate(`/trip/${trip.id}`)}
                  />
                ))
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;
