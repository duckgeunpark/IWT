import React, { useState } from 'react';
import TravelCard from './TravelCard';
import '../styles/TravelSection.css';

const TravelSection = ({ type, travels, onCreateNew, onTravelClick }) => {
  const [sortBy, setSortBy] = useState('latest');

  const isMyTravel = type === 'my';
  const title = isMyTravel ? '내 여행' : '추천 여행';

  // 샘플 데이터 (나중에 props로 받을 데이터)
  const sampleTravels = [
    {
      id: 1,
      date: '24년 05월 12일',
      title: 'LA 부터 시작 하는 든 다 엄마 장에 까지 가는 이제세 복미 여행',
      subtitle: '5박 6일',
      author: '작성자 이름',
      colorTheme: 'green'
    },
    {
      id: 2,
      date: '25년 05월 02일',
      title: '제미있는 맞집 여행',
      subtitle: '1박 2일',
      status: '생성중인 여행',
      colorTheme: 'green'
    },
    {
      id: 3,
      date: '24년 05월 12일',
      title: 'LA 부터 시작 하는 든 다 엄마 장에 까지 가는 이제세 복미 여행',
      subtitle: '5박 6일',
      author: '작성자 이름',
      colorTheme: 'green'
    }
  ];

  const displayTravels = travels || sampleTravels;

  return (
    <div className="travel-section">
      <div className="section-header">
        <h2 className="section-title">{title}</h2>
        <div className="section-actions">
          <button 
            className="view-all-btn"
            onClick={() => console.log('모두 보기 클릭')}
          >
            모두 보기
          </button>
        </div>
      </div>
      
      <div className="travel-grid">
        {isMyTravel && (
          <TravelCard 
            type="create"
            onClick={onCreateNew}
          />
        )}
        
        {displayTravels.map((travel, index) => (
          <TravelCard
            key={travel.id || index}
            type="travel"
            date={travel.date}
            title={travel.title}
            subtitle={travel.subtitle}
            author={travel.author}
            status={travel.status}
            colorTheme={travel.colorTheme}
            onClick={() => onTravelClick && onTravelClick(travel)}
          />
        ))}
      </div>
    </div>
  );
};

export default TravelSection;