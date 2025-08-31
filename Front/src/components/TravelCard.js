import React from 'react';
import '../styles/TravelCard.css';

const TravelCard = ({ 
  type = 'travel', 
  date, 
  title, 
  subtitle, 
  author, 
  status,
  colorTheme = 'green',
  onClick 
}) => {
  if (type === 'create') {
    return (
      <div className="travel-card create-card" onClick={onClick}>
        <div className="create-icon">+</div>
        <div className="create-text">새 여행 만들기</div>
      </div>
    );
  }

  return (
    <div className={`travel-card ${colorTheme}-theme`} onClick={onClick}>
      <div className="card-header">
        <span className="date-badge">{date}</span>
        <span className="duration-badge">{subtitle}</span>
      </div>
      <div className="card-content">
        <h3 className="travel-title">{title}</h3>
      </div>
      <div className="card-footer">
        <span className="author-badge">{author || status}</span>
      </div>
    </div>
  );
};

export default TravelCard;