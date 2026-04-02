import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import TravelSection from '../components/TravelSection';
import '../styles/MainPage.css';

const sortTravels = (travels, sortType) => {
  const sorted = [...travels];
  switch (sortType) {
    case 'oldest':
      return sorted.sort((a, b) => {
        const dateA = a.date.replace(/[년월일\s]/g, '-').replace(/-$/, '');
        const dateB = b.date.replace(/[년월일\s]/g, '-').replace(/-$/, '');
        return new Date(dateA) - new Date(dateB);
      });
    case 'name':
      return sorted.sort((a, b) => a.title.localeCompare(b.title, 'ko'));
    case 'latest':
    default:
      return sorted.sort((a, b) => {
        const dateA = a.date.replace(/[년월일\s]/g, '-').replace(/-$/, '');
        const dateB = b.date.replace(/[년월일\s]/g, '-').replace(/-$/, '');
        return new Date(dateB) - new Date(dateA);
      });
  }
};

const MainPage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const [activeTab, setActiveTab] = useState('all');
  const [sortBy, setSortBy] = useState('latest');

  const allTravels = [
    {
      id: 1,
      date: '24년 05월 12일',
      title: 'LA에서 시작하는 북미 횡단 여행',
      subtitle: '5박 6일',
      author: 'traveler_kim',
      colorTheme: 'blue',
      isMyTravel: false,
      photoCount: 127,
      locationCount: 8
    },
    {
      id: 2,
      date: '25년 05월 02일',
      title: '제주도 맛집 투어',
      subtitle: '1박 2일',
      status: '작성중',
      colorTheme: 'pink',
      isMyTravel: true,
      photoCount: 34,
      locationCount: 5
    },
    {
      id: 3,
      date: '25년 03월 20일',
      title: '도쿄 벚꽃 여행기',
      subtitle: '3박 4일',
      author: 'sakura_fan',
      colorTheme: 'purple',
      isMyTravel: false,
      photoCount: 89,
      locationCount: 12
    },
    {
      id: 4,
      date: '25년 01월 15일',
      title: '방콕 & 치앙마이 배낭여행',
      subtitle: '7박 8일',
      author: 'backpacker_lee',
      colorTheme: 'yellow',
      isMyTravel: false,
      photoCount: 203,
      locationCount: 15
    },
    {
      id: 5,
      date: '24년 12월 25일',
      title: '유럽 크리스마스 마켓 투어',
      subtitle: '5박 6일',
      colorTheme: 'green',
      isMyTravel: true,
      photoCount: 156,
      locationCount: 9
    }
  ];

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const myTravels = useMemo(() => sortTravels(allTravels.filter(t => t.isMyTravel), sortBy), [sortBy]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const recommendedTravels = useMemo(() => sortTravels(allTravels.filter(t => !t.isMyTravel), sortBy), [sortBy]);

  const handleCreateNew = () => {
    if (!isAuthenticated) {
      const shouldLogin = window.confirm('여행 기록을 만들려면 로그인이 필요합니다. 로그인하시겠습니까?');
      if (shouldLogin) {
        loginWithRedirect();
      }
      return;
    }
    navigate('/trip/new');
  };

  const handleTravelClick = (travel) => {
    navigate(`/trip/${travel.id}`);
  };

  if (isLoading) {
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
            <button
              className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              전체
            </button>
            <button
              className={`tab-btn ${activeTab === 'my' ? 'active' : ''}`}
              onClick={() => setActiveTab('my')}
            >
              내 여행
            </button>
            <button
              className={`tab-btn ${activeTab === 'recommended' ? 'active' : ''}`}
              onClick={() => setActiveTab('recommended')}
            >
              추천 여행
            </button>
          </div>

          <div className="content-actions">
            <select
              className="sort-select"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
            >
              <option value="latest">최신 순</option>
              <option value="oldest">오래된 순</option>
              <option value="name">이름 순</option>
            </select>
          </div>
        </div>

        <div className="sections-container">
          {(activeTab === 'all' || activeTab === 'my') && (
            <TravelSection
              type="my"
              travels={myTravels}
              onCreateNew={handleCreateNew}
              onTravelClick={handleTravelClick}
            />
          )}

          {(activeTab === 'all' || activeTab === 'recommended') && (
            <TravelSection
              type="recommended"
              travels={recommendedTravels}
              onTravelClick={handleTravelClick}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default MainPage;