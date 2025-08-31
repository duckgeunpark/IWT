import React, { useState, useEffect, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';
import ImagePanel from '../components/ImagePanel';
import DocumentPanel from '../components/DocumentPanel';
import MapPanel from '../components/MapPanel';
import Resizer from '../components/Resizer';
import '../styles/CreateTripPage.css';

const CreateTripPage = () => {
  const { user, isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const navigate = useNavigate();
  const [tripTitle, setTripTitle] = useState('이름의 2025. 05. 02 ~ 2025. 05. 02 여행 기록');
  const [isEditing, setIsEditing] = useState(false);

  // 인증되지 않은 사용자 리다이렉트
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      // 로그인이 필요하다는 메시지를 표시하고 로그인 페이지로 이동
      alert('게시글을 작성하려면 로그인이 필요합니다.');
      navigate('/');
    }
  }, [isLoading, isAuthenticated, navigate]);
  
  // 패널 너비 상태 (백분율)
  const [leftWidth, setLeftWidth] = useState(25);
  const [centerWidth, setCenterWidth] = useState(50);
  const [rightWidth, setRightWidth] = useState(25);
  
  // 드래그 시작 상태 저장
  const [dragStartState, setDragStartState] = useState({ left: 25, center: 50, right: 25 });
  
  // 반응형 탭 상태 관리
  const [activeTab, setActiveTab] = useState('image'); // 'image', 'document', 'map'
  const [isMobile, setIsMobile] = useState(false);
  
  // 반응형 감지
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 992);
    };
    
    handleResize(); // 초기값 설정
    window.addEventListener('resize', handleResize);
    
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleTitleEdit = () => {
    setIsEditing(true);
  };

  const handleTitleSave = () => {
    setIsEditing(false);
  };

  const handleTitleChange = (e) => {
    setTripTitle(e.target.value);
  };

  const handleTitleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleTitleSave();
    }
  };

  const handleLogoClick = () => {
    navigate('/');
  };

  const handleLeftResize = (totalDeltaX) => {
    const containerWidth = document.querySelector('.panels-container')?.clientWidth || 1200;
    const deltaPercent = (totalDeltaX / containerWidth) * 100;
    
    // 드래그 시작 시점의 실제 상태를 기준으로 계산
    const startLeft = dragStartState.left;
    const startCenter = dragStartState.center;
    const currentRight = rightWidth; // 현재 3번 패널 크기 (고정)
    
    // 3번 패널은 고정, 1번과 2번 패널이 나머지 공간을 나눔
    const availableSpace = 100 - currentRight;
    
    // 1번 패널 크기 조정
    const maxLeftWidth = Math.min(70, availableSpace - 15);
    const newLeftWidth = Math.max(15, Math.min(maxLeftWidth, startLeft + deltaPercent));
    
    // 2번 패널은 나머지 공간 사용
    const newCenterWidth = availableSpace - newLeftWidth;
    
    // 적용
    if (newCenterWidth >= 15) {
      setLeftWidth(newLeftWidth);
      setCenterWidth(newCenterWidth);
    }
  };

  const handleRightResize = (totalDeltaX) => {
    const containerWidth = document.querySelector('.panels-container')?.clientWidth || 1200;
    const deltaPercent = (totalDeltaX / containerWidth) * 100;
    
    // 드래그 시작 시점의 실제 상태를 기준으로 계산
    const currentLeft = leftWidth; // 현재 1번 패널 크기 (고정)
    const startCenter = dragStartState.center;
    const startRight = dragStartState.right;
    
    // 1번 패널은 고정, 2번과 3번 패널이 나머지 공간을 나눔
    const availableSpace = 100 - currentLeft;
    
    // 2번 패널 크기 조정
    const maxCenterWidth = Math.min(70, availableSpace - 15);
    const newCenterWidth = Math.max(15, Math.min(maxCenterWidth, startCenter + deltaPercent));
    
    // 3번 패널은 나머지 공간 사용
    const newRightWidth = availableSpace - newCenterWidth;
    
    // 적용
    if (newRightWidth >= 15) {
      setCenterWidth(newCenterWidth);
      setRightWidth(newRightWidth);
    }
  };

  const handleDragStart = useCallback(() => {
    setDragStartState({ left: leftWidth, center: centerWidth, right: rightWidth });
  }, [leftWidth, centerWidth, rightWidth]);

  const handleDragEnd = useCallback(() => {
    // 드래그 종료 후 즉시 상태 업데이트
    setDragStartState({ left: leftWidth, center: centerWidth, right: rightWidth });
  }, [leftWidth, centerWidth, rightWidth]);

  // 로딩 중이거나 인증되지 않은 경우 처리
  if (isLoading) {
    return (
      <div className="create-trip-page">
        <div className="page-header">
          <div className="header-left">
            <div className="logo-container" onClick={handleLogoClick}>
              <div className="logo-avatar"></div>
              <div className="logo-text">
                <h1>IWT</h1>
                <p>I Want. I Went. Trip.</p>
              </div>
            </div>
          </div>
          <div className="title-section">
            <h1 className="page-title">로딩 중...</h1>
          </div>
        </div>
        <div className="page-content">
          <div style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center', 
            height: '400px',
            fontSize: '18px'
          }}>
            인증 정보를 확인하고 있습니다...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="create-trip-page">
      {/* 헤더 영역 */}
      <div className="page-header">
        <div className="header-left">
          <div className="logo-container" onClick={handleLogoClick}>
            <div className="logo-avatar"></div>
            <div className="logo-text">
              <h1>IWT</h1>
              <p>I Want. I Went. Trip.</p>
            </div>
          </div>
        </div>
        
        <div className="title-section">
          {isEditing ? (
            <input
              type="text"
              className="title-input"
              value={tripTitle}
              onChange={handleTitleChange}
              onBlur={handleTitleSave}
              onKeyPress={handleTitleKeyPress}
              autoFocus
            />
          ) : (
            <h1 className="page-title" onClick={handleTitleEdit}>
              {tripTitle}
            </h1>
          )}
        </div>
        
        <div className="header-actions">
          <button className="action-btn temp-save-btn">임시저장</button>
          <button className="action-btn upload-btn">업로드</button>
          <div className="user-profile-icon">
            {isAuthenticated && user?.picture ? (
              <img src={user.picture} alt="프로필" className="profile-img" />
            ) : (
              <div className="default-profile">👤</div>
            )}
          </div>
        </div>
      </div>

      {/* 메인 콘텐츠 영역 */}
      <div className="page-content">
        {/* 반응형 탭 메뉴 */}
        {isMobile && (
          <div className="tab-menu">
          <button 
            className={`tab-button ${activeTab === 'image' ? 'active' : ''}`}
            onClick={() => setActiveTab('image')}
          >
            📷 사진
          </button>
          <button 
            className={`tab-button ${activeTab === 'document' ? 'active' : ''}`}
            onClick={() => setActiveTab('document')}
          >
            📄 문서
          </button>
          <button 
            className={`tab-button ${activeTab === 'map' ? 'active' : ''}`}
            onClick={() => setActiveTab('map')}
          >
            🗺️ 지도
          </button>
          </div>
        )}
        
        <div className="panels-container">
          {/* 왼쪽 패널 - 이미지 */}
          <div 
            className={`panel-wrapper left-panel ${isMobile && activeTab !== 'image' ? 'mobile-hidden' : ''}`} 
            style={{ width: isMobile ? '100%' : `${leftWidth}%` }}
          >
            <ImagePanel />
          </div>

          {!isMobile && (
            <Resizer 
              onResize={handleLeftResize} 
              onStart={handleDragStart} 
              onEnd={handleDragEnd}
              style={{ left: `${leftWidth}%` }}
            />
          )}

          {/* 중간 패널 - 문서 */}
          <div 
            className={`panel-wrapper center-panel ${isMobile && activeTab !== 'document' ? 'mobile-hidden' : ''}`} 
            style={{ width: isMobile ? '100%' : `${centerWidth}%` }}
          >
            <DocumentPanel />
          </div>

          {!isMobile && (
            <Resizer 
              onResize={handleRightResize} 
              onStart={handleDragStart} 
              onEnd={handleDragEnd}
              style={{ left: `${leftWidth + centerWidth}%` }}
            />
          )}

          {/* 오른쪽 패널 - 지도 */}
          <div 
            className={`panel-wrapper right-panel ${isMobile && activeTab !== 'map' ? 'mobile-hidden' : ''}`} 
            style={{ width: isMobile ? '100%' : `${rightWidth}%` }}
          >
            <MapPanel />
          </div>
        </div>
      </div>

    </div>
  );
};

export default CreateTripPage;