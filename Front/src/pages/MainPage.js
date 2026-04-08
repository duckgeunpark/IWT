import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import TravelSection from '../components/TravelSection';
import { apiClient } from '../services/apiClient';
import '../styles/MainPage.css';

const COLOR_THEMES = ['blue', 'pink', 'purple', 'yellow', 'green', 'orange'];

function formatDate(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  const y = String(d.getFullYear()).slice(2);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}년 ${m}월 ${day}일`;
}

function mapPost(post, index, isMyTravel) {
  return {
    id: post.id,
    date: formatDate(post.created_at),
    title: post.title,
    subtitle: post.tags?.[0] || `${post.photo_count || 0}장`,
    author: isMyTravel ? undefined : (post.user_id || '').split('|').pop()?.slice(0, 12),
    colorTheme: COLOR_THEMES[index % COLOR_THEMES.length],
    isMyTravel,
    photoCount: post.photo_count || 0,
    locationCount: 0,
    status: undefined,
  };
}

const sortTravels = (travels, sortType) => {
  const sorted = [...travels];
  switch (sortType) {
    case 'oldest':
      return sorted.sort((a, b) => new Date(a.date.replace(/[년월일\s]/g, '-').replace(/-$/, '')) - new Date(b.date.replace(/[년월일\s]/g, '-').replace(/-$/, '')));
    case 'name':
      return sorted.sort((a, b) => a.title.localeCompare(b.title, 'ko'));
    case 'latest':
    default:
      return sorted.sort((a, b) => new Date(b.date.replace(/[년월일\s]/g, '-').replace(/-$/, '')) - new Date(a.date.replace(/[년월일\s]/g, '-').replace(/-$/, '')));
  }
};

const MainPage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: authLoading, loginWithRedirect, user } = useAuth0();
  const [activeTab, setActiveTab] = useState('all');
  const [sortBy, setSortBy] = useState('latest');
  const [myPosts, setMyPosts] = useState([]);
  const [publicPosts, setPublicPosts] = useState([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (authLoading) return;

    const loadData = async () => {
      setDataLoading(true);
      setError(null);
      try {
        // 공개 게시글 (추천 여행)
        const publicRes = await apiClient.get('/api/v1/posts?skip=0&limit=20');
        const allPublic = (publicRes?.posts || []).map((p, i) => mapPost(p, i, false));

        if (isAuthenticated && user?.sub) {
          // 내 게시글
          const myRes = await apiClient.get(`/api/v1/posts/user/${encodeURIComponent(user.sub)}?skip=0&limit=50`);
          const myIds = new Set((myRes?.posts || []).map(p => p.id));
          setMyPosts((myRes?.posts || []).map((p, i) => mapPost(p, i, true)));
          // 추천: 내 게시글 제외
          setPublicPosts(allPublic.filter(p => !myIds.has(p.id)));
        } else {
          setMyPosts([]);
          setPublicPosts(allPublic);
        }
      } catch (err) {
        console.error('게시글 로드 실패:', err);
        setError('게시글을 불러오는 데 실패했습니다.');
      } finally {
        setDataLoading(false);
      }
    };

    loadData();
  }, [authLoading, isAuthenticated, user]);

  const sortedMyTravels = useMemo(() => sortTravels(myPosts, sortBy), [myPosts, sortBy]);
  const sortedRecommended = useMemo(() => sortTravels(publicPosts, sortBy), [publicPosts, sortBy]);

  const handleCreateNew = () => {
    if (!isAuthenticated) {
      const shouldLogin = window.confirm('여행 기록을 만들려면 로그인이 필요합니다. 로그인하시겠습니까?');
      if (shouldLogin) loginWithRedirect();
      return;
    }
    navigate('/trip/new');
  };

  const handleTravelClick = (travel) => {
    navigate(`/trip/${travel.id}`);
  };

  if (authLoading) {
    return (
      <div className="main-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="main-content">
          <div className="page-loading">
            <div className="page-loading-spinner" />
            <p>인증 상태를 확인하는 중...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="main-content">
        {/* Hero Section */}
        <div className="hero-section">
          <div className="hero-content">
            <h2 className="hero-title">
              여행의 순간을 <span className="gradient-text">기록</span>하세요
            </h2>
            <p className="hero-subtitle">
              사진을 업로드하면 AI가 자동으로 여행 기록을 만들어 드립니다
            </p>
            <button className="hero-cta" onClick={handleCreateNew}>
              새 여행 기록 만들기
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="content-header">
          <div className="tab-container">
            <button className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`} onClick={() => setActiveTab('all')}>전체</button>
            <button className={`tab-btn ${activeTab === 'my' ? 'active' : ''}`} onClick={() => setActiveTab('my')}>내 여행</button>
            <button className={`tab-btn ${activeTab === 'recommended' ? 'active' : ''}`} onClick={() => setActiveTab('recommended')}>추천 여행</button>
          </div>
          <div className="content-actions">
            <select className="sort-select" value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="latest">최신 순</option>
              <option value="oldest">오래된 순</option>
              <option value="name">이름 순</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="error-banner" style={{ padding: '12px 24px', color: 'var(--color-error)', background: 'var(--color-error-bg, #fff0f0)', borderRadius: '8px', margin: '0 0 16px' }}>
            {error}
          </div>
        )}

        {dataLoading ? (
          <div className="page-loading" style={{ padding: '48px 0' }}>
            <div className="page-loading-spinner" />
            <p>게시글을 불러오는 중...</p>
          </div>
        ) : (
          <div className="sections-container">
            {(activeTab === 'all' || activeTab === 'my') && (
              <>
                <TravelSection
                  type="my"
                  travels={sortedMyTravels}
                  onCreateNew={handleCreateNew}
                  onTravelClick={handleTravelClick}
                />
                {isAuthenticated && sortedMyTravels.length === 0 && sortedRecommended.length > 0 && (
                  <div className="follower-feed-empty">
                    <p className="follower-feed-empty-msg">아직 팔로잉하는 사람이 없어요. 이런 여행은 어떠세요?</p>
                    <TravelSection
                      type="recommended"
                      travels={sortedRecommended.slice(0, 6)}
                      onTravelClick={handleTravelClick}
                    />
                  </div>
                )}
              </>
            )}
            {(activeTab === 'all' || activeTab === 'recommended') && (
              <TravelSection
                type="recommended"
                travels={sortedRecommended}
                onTravelClick={handleTravelClick}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default MainPage;
