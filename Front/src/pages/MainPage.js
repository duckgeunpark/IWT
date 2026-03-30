import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import TravelSection from '../components/TravelSection';
import '../styles/MainPage.css';

const MainPage = () => {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const [activeTab, setActiveTab] = useState('all');
  const [sortBy, setSortBy] = useState('latest');

  // 샘플 데이터 (나중에 API에서 가져올 데이터)
  const allTravels = [
    {
      id: 1,
      date: '24년 05월 12일',
      title: 'LA 부터 시작 하는 든 다 엄마 장에 까지 가는 이제세 복미 여행',
      subtitle: '5박 6일',
      author: '작성자 이름',
      colorTheme: 'green',
      isMyTravel: false
    },
    {
      id: 2,
      date: '25년 05월 02일',
      title: '제미있는 맞집 여행',
      subtitle: '1박 2일',
      status: '생성중인 여행',
      colorTheme: 'green',
      isMyTravel: true
    },
    {
      id: 3,
      date: '24년 05월 12일',
      title: 'LA 부터 시작 하는 든 다 엄마 장에 까지 가는 이제세 복미 여행',
      subtitle: '5박 6일',
      author: '작성자 이름',
      colorTheme: 'green',
      isMyTravel: true
    }
  ];

  const myTravels = allTravels.filter(travel => travel.isMyTravel);
  const recommendedTravels = allTravels.filter(travel => !travel.isMyTravel);

  const handleCreateNew = () => {
    if (!isAuthenticated) {
      // 로그인하지 않은 사용자에게 로그인 요구
      const shouldLogin = window.confirm('여행 기록을 만들려면 로그인이 필요합니다. 로그인하시겠습니까?');
      if (shouldLogin) {
        loginWithRedirect();
      }
      return;
    }
    navigate('/create-trip');
  };

  const handleTravelClick = (travel) => {
    navigate('/create-trip', { state: { travel } });
  };

  const handleSortChange = (newSort) => {
    setSortBy(newSort);
    // TODO: 정렬 로직
  };

  if (isLoading) {
    return (
      <div className="main-page">
        <Header />
        <div className="main-content">
          <div style={{ textAlign: 'center', padding: '50px' }}>
            <p>인증 상태를 확인하는 중...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-page">
      <Header />
      
      <div className="main-content">
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
              onChange={(e) => handleSortChange(e.target.value)}
            >
              <option value="latest">정렬</option>
              <option value="oldest">오래된 순</option>
              <option value="name">이름 순</option>
            </select>
            <button 
              className="create-new-btn"
              onClick={handleCreateNew}
            >
              + 새로 만들기
            </button>
          </div>
        </div>

        <div className="sections-container">
          {(activeTab === 'all' || activeTab === 'recommended') && (
            <TravelSection 
              type="recommended"
              travels={recommendedTravels}
              onTravelClick={handleTravelClick}
            />
          )}
          
          {(activeTab === 'all' || activeTab === 'my') && (
            <TravelSection 
              type="my"
              travels={myTravels}
              onCreateNew={handleCreateNew}
              onTravelClick={handleTravelClick}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default MainPage;