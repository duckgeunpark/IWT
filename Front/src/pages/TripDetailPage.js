import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import Header from '../components/Header';
import MarkdownPreview from '../components/MarkdownPreview';
import '../styles/TripDetailPage.css';

// 샘플 데이터 (나중에 API로 대체)
const SAMPLE_TRIPS = {
  1: {
    id: 1,
    title: 'LA에서 시작하는 북미 횡단 여행',
    author: { name: 'traveler_kim', picture: null },
    date: '2024-05-12',
    duration: '5박 6일',
    colorTheme: 'blue',
    photoCount: 127,
    locationCount: 8,
    likes: 342,
    saves: 89,
    photos: [
      { id: 1, url: null, caption: 'Santa Monica Beach', location: 'Santa Monica, CA' },
      { id: 2, url: null, caption: 'Grand Canyon Sunset', location: 'Grand Canyon, AZ' },
      { id: 3, url: null, caption: 'Route 66', location: 'Williams, AZ' },
      { id: 4, url: null, caption: 'Las Vegas Strip', location: 'Las Vegas, NV' },
    ],
    locations: [
      { id: 1, name: 'Santa Monica Beach', lat: 34.0195, lng: -118.4912, day: 1 },
      { id: 2, name: 'Grand Canyon', lat: 36.1069, lng: -112.1129, day: 2 },
      { id: 3, name: 'Route 66 Museum', lat: 35.2495, lng: -112.1871, day: 3 },
      { id: 4, name: 'Las Vegas Strip', lat: 36.1147, lng: -115.1728, day: 4 },
    ],
    content: `# LA에서 시작하는 북미 횡단 여행

## 1일차 — Santa Monica Beach

캘리포니아의 해변에서 여행이 시작되었습니다. 새벽에 도착해서 일출을 볼 수 있었어요.

> "여행의 시작은 언제나 설레는 법이다."

## 2일차 — Grand Canyon

말로 표현할 수 없는 웅장함. 사진으로는 절대 담을 수 없는 스케일이었습니다.

## 3일차 — Route 66

미국의 어머니 도로를 따라 달렸습니다. 복고풍 주유소와 다이너가 마치 영화 속 한 장면 같았어요.

## 4일차 — Las Vegas

네온사인이 빛나는 도시. 밤의 라스베가스는 정말 다른 세상이었습니다.

---

*총 127장의 사진과 8개의 위치가 기록되었습니다.*
`,
    tags: ['북미', '로드트립', 'LA', '그랜드캐년', '라스베가스'],
  },
  2: {
    id: 2,
    title: '제주도 맛집 투어',
    author: { name: 'me', picture: null },
    date: '2025-05-02',
    duration: '1박 2일',
    colorTheme: 'pink',
    photoCount: 34,
    locationCount: 5,
    likes: 0,
    saves: 0,
    status: '작성중',
    photos: [],
    locations: [],
    content: '# 제주도 맛집 투어\n\n작성 중...',
    tags: ['제주도', '맛집'],
  },
};

const TripDetailPage = ({ toggleTheme, theme }) => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth0();
  const [trip, setTrip] = useState(null);
  const [isLiked, setIsLiked] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [activePhotoIndex, setActivePhotoIndex] = useState(0);
  const [showMap, setShowMap] = useState(false);

  useEffect(() => {
    // TODO: API에서 여행 데이터 가져오기
    const tripData = SAMPLE_TRIPS[id];
    if (tripData) {
      setTrip(tripData);
    }
  }, [id]);

  if (!trip) {
    return (
      <div className="trip-detail-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="trip-detail-loading">
          <div className="page-loading-spinner" />
          <p>여행 기록을 불러오는 중...</p>
        </div>
      </div>
    );
  }

  const isOwner = isAuthenticated && trip.author?.name === 'me';

  return (
    <div className="trip-detail-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="trip-detail-container">
        {/* Left: Photo Gallery */}
        <div className="trip-gallery">
          <div className={`gallery-hero ${trip.colorTheme}-gradient`}>
            {trip.photos.length > 0 && trip.photos[activePhotoIndex]?.url ? (
              <img
                src={trip.photos[activePhotoIndex].url}
                alt={trip.photos[activePhotoIndex].caption}
                className="gallery-hero-img"
              />
            ) : (
              <div className="gallery-placeholder">
                <div className="gallery-placeholder-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="m21 15-5-5L5 21" />
                  </svg>
                </div>
                <p>{trip.photoCount}장의 사진</p>
              </div>
            )}

            {/* Photo Navigation Dots */}
            {trip.photos.length > 1 && (
              <div className="gallery-dots">
                {trip.photos.slice(0, 5).map((_, i) => (
                  <button
                    key={i}
                    className={`gallery-dot ${i === activePhotoIndex ? 'active' : ''}`}
                    onClick={() => setActivePhotoIndex(i)}
                  />
                ))}
                {trip.photos.length > 5 && <span className="gallery-dots-more">+{trip.photos.length - 5}</span>}
              </div>
            )}
          </div>

          {/* Photo Thumbnails */}
          {trip.photos.length > 1 && (
            <div className="gallery-thumbs">
              {trip.photos.map((photo, i) => (
                <button
                  key={photo.id}
                  className={`gallery-thumb ${i === activePhotoIndex ? 'active' : ''}`}
                  onClick={() => setActivePhotoIndex(i)}
                >
                  {photo.url ? (
                    <img src={photo.url} alt={photo.caption} />
                  ) : (
                    <div className="thumb-placeholder">{i + 1}</div>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Trip Info */}
        <div className="trip-info">
          {/* Author Header */}
          <div className="trip-info-header">
            <div className="trip-author" onClick={() => navigate(`/profile`)}>
              <div className="author-avatar-ring">
                {trip.author?.picture ? (
                  <img src={trip.author.picture} alt="" className="author-avatar-img" />
                ) : (
                  <div className="author-avatar-default">
                    {(trip.author?.name || '?')[0].toUpperCase()}
                  </div>
                )}
              </div>
              <div className="author-meta">
                <span className="author-name">{trip.author?.name || '익명'}</span>
                <span className="trip-location-label">{trip.locations[0]?.name || ''}</span>
              </div>
            </div>
            {isOwner && (
              <button className="trip-edit-btn" onClick={() => navigate(`/trip/${id}/edit`)}>
                편집
              </button>
            )}
          </div>

          {/* Trip Title & Meta */}
          <div className="trip-title-section">
            <h1 className="trip-title">{trip.title}</h1>
            <div className="trip-meta">
              <span className="trip-meta-item">{trip.date}</span>
              <span className="trip-meta-divider">&middot;</span>
              <span className="trip-meta-item">{trip.duration}</span>
              <span className="trip-meta-divider">&middot;</span>
              <span className="trip-meta-item">{trip.photoCount}장</span>
              <span className="trip-meta-divider">&middot;</span>
              <span className="trip-meta-item">{trip.locationCount}곳</span>
            </div>
            {trip.status && <span className="trip-status-badge">{trip.status}</span>}
          </div>

          {/* Actions (Instagram-style) */}
          <div className="trip-actions">
            <div className="trip-actions-left">
              <button
                className={`action-icon-btn ${isLiked ? 'liked' : ''}`}
                onClick={() => setIsLiked(!isLiked)}
              >
                <svg width="24" height="24" viewBox="0 0 24 24" fill={isLiked ? '#ed4956' : 'none'} stroke={isLiked ? '#ed4956' : 'currentColor'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                </svg>
              </button>
              <button className="action-icon-btn" onClick={() => setShowMap(!showMap)}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                  <circle cx="12" cy="10" r="3" />
                </svg>
              </button>
              <button className="action-icon-btn">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
            <button
              className={`action-icon-btn ${isSaved ? 'saved' : ''}`}
              onClick={() => setIsSaved(!isSaved)}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill={isSaved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
              </svg>
            </button>
          </div>

          {/* Likes */}
          {(trip.likes > 0 || isLiked) && (
            <div className="trip-likes">
              <strong>{trip.likes + (isLiked ? 1 : 0)}</strong>명이 좋아합니다
            </div>
          )}

          {/* Map Toggle */}
          {showMap && trip.locations.length > 0 && (
            <div className="trip-map-preview">
              <div className="trip-map-route">
                {trip.locations.map((loc, i) => (
                  <div key={loc.id} className="route-stop">
                    <div className="route-stop-marker">
                      <span>{i + 1}</span>
                    </div>
                    <div className="route-stop-info">
                      <span className="route-stop-name">{loc.name}</span>
                      <span className="route-stop-day">Day {loc.day}</span>
                    </div>
                    {i < trip.locations.length - 1 && <div className="route-connector" />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Content */}
          <div className="trip-content-area">
            <MarkdownPreview content={trip.content} />
          </div>

          {/* Tags */}
          {trip.tags?.length > 0 && (
            <div className="trip-tags">
              {trip.tags.map((tag) => (
                <span key={tag} className="trip-tag">#{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TripDetailPage;
