import React from 'react';
import TravelCard from './TravelCard';
import '../styles/TravelSection.css';

const TravelSection = ({ type, travels = [], onCreateNew, onTravelClick }) => {
  const isMyTravel = type === 'my';
  const title = isMyTravel ? '내 여행' : '추천 여행';

  return (
    <div className="travel-section">
      <div className="section-header">
        <h2 className="section-title">{title}</h2>
        {travels.length > 3 && (
          <div className="section-actions">
            <button className="view-all-btn" onClick={() => {}}>
              모두 보기
            </button>
          </div>
        )}
      </div>

      <div className="travel-grid">
        {isMyTravel && (
          <TravelCard
            type="create"
            onClick={onCreateNew}
          />
        )}

        {travels.map((travel, index) => (
          <TravelCard
            key={travel.id || index}
            type="travel"
            date={travel.date}
            title={travel.title}
            subtitle={travel.subtitle}
            author={travel.author}
            status={travel.status}
            colorTheme={travel.colorTheme}
            photoCount={travel.photoCount}
            locationCount={travel.locationCount}
            thumbnailUrl={travel.thumbnailUrl}
            likesCount={travel.likesCount}
            commentsCount={travel.commentsCount}
            onClick={() => onTravelClick && onTravelClick(travel)}
          />
        ))}
      </div>
    </div>
  );
};

export default TravelSection;
