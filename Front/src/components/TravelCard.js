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
  photoCount,
  locationCount,
  thumbnailUrl,
  likesCount,
  commentsCount,
  onClick
}) => {
  if (type === 'create') {
    return (
      <div className="travel-card create-card" onClick={onClick}>
        <div className="create-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </div>
        <div className="create-text">새 여행 만들기</div>
        <div className="create-hint">사진을 업로드하고 AI로 기록하세요</div>
      </div>
    );
  }

  return (
    <div className={`travel-card ${colorTheme}-theme`} onClick={onClick}>
      {thumbnailUrl && (
        <div className="card-thumbnail">
          <img src={thumbnailUrl} alt={title} />
        </div>
      )}
      <div className="card-header">
        {status && <span className="status-badge">{status}</span>}
        <span className="date-badge">{date}</span>
        <span className="duration-badge">{subtitle}</span>
      </div>
      <div className="card-content">
        <h3 className="travel-title">{title}</h3>
      </div>
      <div className="card-footer">
        <div className="card-stats">
          {photoCount > 0 && (
            <span className="stat-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg>
              {photoCount}
            </span>
          )}
          {locationCount > 0 && (
            <span className="stat-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
              {locationCount}
            </span>
          )}
          {likesCount > 0 && (
            <span className="stat-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
              {likesCount}
            </span>
          )}
          {commentsCount > 0 && (
            <span className="stat-item">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              {commentsCount}
            </span>
          )}
        </div>
        {author && (
          <span className="author-badge">
            <span className="author-avatar">{String(author)[0]?.toUpperCase()}</span>
            {author}
          </span>
        )}
      </div>
    </div>
  );
};

export default TravelCard;
