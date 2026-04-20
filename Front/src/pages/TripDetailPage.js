import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { useDispatch, useSelector } from 'react-redux';
import Header from '../components/Header';
import MarkdownPreview from '../components/MarkdownPreview';
import {
  fetchPostSocialInfo,
  toggleLike,
  toggleBookmark,
  fetchComments,
  createComment,
  deleteComment,
  toggleFollow,
} from '../store/socialSlice';
import { apiClient } from '../services/apiClient';
import { formatDate } from '../utils/dateUtils';
import '../styles/TripDetailPage.css';

const GOOGLE_MAPS_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

const TripDetailPage = ({ toggleTheme, theme }) => {
  const { id } = useParams();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { isAuthenticated, user } = useAuth0();
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);

  const [trip, setTrip] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activePhotoIndex, setActivePhotoIndex] = useState(0);
  const [commentText, setCommentText] = useState('');
  const [showComments, setShowComments] = useState(false);
  const [similarPosts, setSimilarPosts] = useState([]);

  const postId = parseInt(id);
  const social = useSelector((state) => state.social.postSocial[postId] || {});
  const commentsData = useSelector((state) => state.social.postComments[postId] || { comments: [], total: 0 });
  const followStatus = useSelector((state) => state.social.followStatus);

  const isLiked = social.is_liked || false;
  const isSaved = social.is_bookmarked || false;
  const likesCount = social.likes_count || 0;
  const commentsCount = social.comments_count || 0;

  // 게시글 + 사진 로드
  useEffect(() => {
    const loadTrip = async () => {
      try {
        const [tripData, photosData] = await Promise.all([
          apiClient.get(`/api/v1/posts/${postId}`),
          apiClient.get(`/api/v1/posts/${postId}/photos`).catch(() => ({ photos: [] })),
        ]);
        setTrip(tripData);
        setPhotos(photosData?.photos || []);
        dispatch(fetchPostSocialInfo(postId));
        // 유사 여행 추천 (백그라운드)
        apiClient.get(`/api/v1/posts/${postId}/similar?limit=4`)
          .then(res => setSimilarPosts(res?.posts || []))
          .catch(() => {});
      } catch (err) {
        console.error('게시글 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    };
    loadTrip();
  }, [postId, dispatch]);

  // 댓글 영역 열 때 로드
  useEffect(() => {
    if (showComments) {
      dispatch(fetchComments({ postId }));
    }
  }, [showComments, postId, dispatch]);

  // 지도 초기화
  useEffect(() => {
    if (!mapRef.current || !GOOGLE_MAPS_KEY) return;
    if (mapInstanceRef.current) return;

    const gpsPhotos = photos.filter(p => p.location?.lat && p.location?.lng);
    if (gpsPhotos.length === 0) return;

    const initMap = () => {
      const center = {
        lat: gpsPhotos[0].location.lat,
        lng: gpsPhotos[0].location.lng,
      };
      const map = new window.google.maps.Map(mapRef.current, {
        center,
        zoom: 10,
        mapTypeId: 'roadmap',
      });
      mapInstanceRef.current = map;

      // 마커 추가
      const bounds = new window.google.maps.LatLngBounds();
      gpsPhotos.forEach((photo, i) => {
        const pos = { lat: photo.location.lat, lng: photo.location.lng };
        new window.google.maps.Marker({
          position: pos,
          map,
          label: String(i + 1),
          title: photo.location.city || photo.file_name,
        });
        bounds.extend(pos);
      });

      // 경로 선 그리기
      if (gpsPhotos.length > 1) {
        const path = gpsPhotos.map(p => ({ lat: p.location.lat, lng: p.location.lng }));
        new window.google.maps.Polyline({
          path,
          geodesic: true,
          strokeColor: '#4285F4',
          strokeOpacity: 0.8,
          strokeWeight: 3,
          map,
        });
      }

      map.fitBounds(bounds);
    };

    if (window.google?.maps) {
      initMap();
    } else {
      const existingScript = document.getElementById('google-maps-script');
      if (!existingScript) {
        const script = document.createElement('script');
        script.id = 'google-maps-script';
        script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_KEY}`;
        script.async = true;
        script.onload = initMap;
        document.head.appendChild(script);
      } else {
        existingScript.addEventListener('load', initMap);
      }
    }
  }, [photos]);

  const handleLike = useCallback(() => {
    if (!isAuthenticated) return;
    dispatch(toggleLike(postId));
  }, [dispatch, postId, isAuthenticated]);

  const handleBookmark = useCallback(() => {
    if (!isAuthenticated) return;
    dispatch(toggleBookmark(postId));
  }, [dispatch, postId, isAuthenticated]);

  const handleCommentSubmit = useCallback(
    (e) => {
      e.preventDefault();
      if (!commentText.trim() || !isAuthenticated) return;
      dispatch(createComment({ postId, content: commentText.trim() }));
      setCommentText('');
    },
    [dispatch, postId, commentText, isAuthenticated]
  );

  const handleDeleteComment = useCallback(
    (commentId) => {
      dispatch(deleteComment({ postId, commentId }));
    },
    [dispatch, postId]
  );

  const handleFollow = useCallback(() => {
    if (!isAuthenticated || !trip) return;
    dispatch(toggleFollow(trip.user_id));
  }, [dispatch, trip, isAuthenticated]);

  const isFollowing = trip ? followStatus[trip.user_id]?.following : false;

  const handleShare = useCallback(() => {
    const url = window.location.href;
    if (navigator.share) {
      navigator.share({ title: trip?.title || '여행 기록', url });
    } else {
      navigator.clipboard.writeText(url).then(() => {
        alert('링크가 복사됐습니다!');
      });
    }
  }, [trip]);

  if (loading) {
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

  if (!trip) {
    return (
      <div className="trip-detail-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="trip-detail-loading">
          <p>게시글을 찾을 수 없습니다.</p>
          <button onClick={() => navigate('/explore')} className="trip-edit-btn">
            탐색으로 돌아가기
          </button>
        </div>
      </div>
    );
  }

  const isOwner = isAuthenticated && trip.user_id === user?.sub;
  const tags = Array.isArray(trip.tags) ? trip.tags : [];
  const activePhoto = photos[activePhotoIndex];
  const gpsPhotos = photos.filter(p => p.location?.lat && p.location?.lng);

  return (
    <div className="trip-detail-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="trip-detail-container">
        {/* Left: Photo Gallery + Map */}
        <div className="trip-gallery">
          {/* 사진 캐러셀 */}
          <div className="gallery-photos">
            {photos.length > 0 ? (
              <>
                <div className="gallery-main">
                  <img
                    src={activePhoto?.url}
                    alt={activePhoto?.file_name || '여행 사진'}
                    className="gallery-main-img"
                    style={{ width: '100%', height: '360px', objectFit: 'cover', display: 'block' }}
                  />
                  {photos.length > 1 && (
                    <>
                      <button
                        className="gallery-nav gallery-nav-prev"
                        onClick={() => setActivePhotoIndex(i => (i - 1 + photos.length) % photos.length)}
                        style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', background: 'rgba(0,0,0,0.45)', border: 'none', borderRadius: '50%', width: 36, height: 36, cursor: 'pointer', color: '#fff', fontSize: 18 }}
                      >‹</button>
                      <button
                        className="gallery-nav gallery-nav-next"
                        onClick={() => setActivePhotoIndex(i => (i + 1) % photos.length)}
                        style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'rgba(0,0,0,0.45)', border: 'none', borderRadius: '50%', width: 36, height: 36, cursor: 'pointer', color: '#fff', fontSize: 18 }}
                      >›</button>
                      <div className="gallery-counter" style={{ position: 'absolute', bottom: 12, right: 16, background: 'rgba(0,0,0,0.5)', color: '#fff', padding: '2px 8px', borderRadius: 10, fontSize: 12 }}>
                        {activePhotoIndex + 1} / {photos.length}
                      </div>
                    </>
                  )}
                </div>
                {photos.length > 1 && (
                  <div className="gallery-strip" style={{ display: 'flex', gap: 6, padding: '6px 8px', overflowX: 'auto' }}>
                    {photos.map((photo, i) => (
                      <img
                        key={photo.id}
                        src={photo.url}
                        alt=""
                        onClick={() => setActivePhotoIndex(i)}
                        style={{
                          width: 56, height: 56, objectFit: 'cover', borderRadius: 6, cursor: 'pointer', flexShrink: 0,
                          border: i === activePhotoIndex ? '2px solid var(--color-primary, #4285F4)' : '2px solid transparent',
                          opacity: i === activePhotoIndex ? 1 : 0.65,
                        }}
                      />
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="gallery-hero blue-gradient">
                <div className="gallery-placeholder">
                  <div className="gallery-placeholder-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2" />
                      <circle cx="8.5" cy="8.5" r="1.5" />
                      <path d="m21 15-5-5L5 21" />
                    </svg>
                  </div>
                  <p>{trip.photo_count || 0}장의 사진</p>
                </div>
              </div>
            )}
          </div>

          {/* 지도 (GPS 사진 있을 때만) */}
          {gpsPhotos.length > 0 && (
            <div className="gallery-map" ref={mapRef} />
          )}
        </div>

        {/* Right: Trip Info */}
        <div className="trip-info">
          {/* Author Header */}
          <div className="trip-info-header">
            <div
              className="trip-author"
              style={{ cursor: 'pointer' }}
              onClick={() => navigate(`/profile/${encodeURIComponent(trip.user_id)}`)}
            >
              <div className="author-avatar-ring">
                {trip.author?.picture ? (
                  <img src={trip.author.picture} alt="" className="author-avatar-img" />
                ) : (
                  <div className="author-avatar-default">
                    {(trip.author?.name || trip.user_id || '?')[0].toUpperCase()}
                  </div>
                )}
              </div>
              <div className="author-meta">
                <span className="author-name">
                  {trip.author?.name || trip.user_id?.split('|').pop()?.slice(0, 16) || trip.user_id}
                </span>
              </div>
            </div>
            <div className="trip-header-actions">
              {isOwner ? (
                <button className="trip-edit-btn" onClick={() => navigate(`/trip/${id}/edit`)}>
                  편집
                </button>
              ) : isAuthenticated && (
                <button
                  className={`follow-btn ${isFollowing ? 'following' : ''}`}
                  onClick={handleFollow}
                >
                  {isFollowing ? '팔로잉' : '팔로우'}
                </button>
              )}
            </div>
          </div>

          {/* Trip Title & Meta */}
          <div className="trip-title-section">
            <h1 className="trip-title">{trip.title}</h1>
            <div className="trip-meta">
              <span className="trip-meta-item">{formatDate(trip.created_at)}</span>
              <span className="trip-meta-divider">&middot;</span>
              <span className="trip-meta-item">{trip.photo_count || 0}장</span>
            </div>
          </div>

          {/* Actions (Instagram-style) */}
          <div className="trip-actions">
            <div className="trip-actions-left">
              <button className={`action-icon-btn ${isLiked ? 'liked' : ''}`} onClick={handleLike}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill={isLiked ? '#ed4956' : 'none'} stroke={isLiked ? '#ed4956' : 'currentColor'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                </svg>
              </button>
              <button className="action-icon-btn" onClick={() => setShowComments(!showComments)}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </button>
              <button className="action-icon-btn" onClick={handleShare} title="공유">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
            <button className={`action-icon-btn ${isSaved ? 'saved' : ''}`} onClick={handleBookmark}>
              <svg width="24" height="24" viewBox="0 0 24 24" fill={isSaved ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
              </svg>
            </button>
          </div>

          {/* Likes */}
          {likesCount > 0 && (
            <div className="trip-likes">
              <strong>{likesCount}</strong>명이 좋아합니다
            </div>
          )}

          {/* Content */}
          <div className="trip-content-area">
            {trip.description ? (
              <MarkdownPreview content={trip.description} />
            ) : (
              <p className="trip-no-content">내용이 없습니다.</p>
            )}
          </div>

          {/* Tags */}
          {tags.length > 0 && (
            <div className="trip-tags">
              {tags.map((tag) => (
                <span key={tag} className="trip-tag">#{tag}</span>
              ))}
            </div>
          )}

          {/* Comments Section */}
          {showComments && (
            <div className="trip-comments-section">
              <div className="comments-header">
                <h4>댓글 {commentsCount > 0 && <span className="comments-count">{commentsCount}</span>}</h4>
              </div>
              {isAuthenticated && (
                <form className="comment-form" onSubmit={handleCommentSubmit}>
                  <input
                    type="text"
                    className="comment-input"
                    placeholder="댓글을 입력하세요..."
                    value={commentText}
                    onChange={(e) => setCommentText(e.target.value)}
                  />
                  <button type="submit" className="comment-submit-btn" disabled={!commentText.trim()}>
                    게시
                  </button>
                </form>
              )}
              <div className="comment-list">
                {commentsData.comments.map((comment) => (
                  <div key={comment.id} className="comment-item">
                    <div className="comment-avatar">
                      {comment.author?.picture ? (
                        <img src={comment.author.picture} alt="" />
                      ) : (
                        <div className="comment-avatar-default">
                          {(comment.author?.name || comment.user_id || '?')[0].toUpperCase()}
                        </div>
                      )}
                    </div>
                    <div className="comment-body">
                      <span className="comment-author-name">{comment.author?.name || comment.user_id}</span>
                      <span className="comment-text">{comment.content}</span>
                      <div className="comment-meta">
                        <span className="comment-time">{formatDate(comment.created_at)}</span>
                        {comment.user_id === user?.sub && (
                          <button className="comment-delete-btn" onClick={() => handleDeleteComment(comment.id)}>삭제</button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {commentsData.comments.length === 0 && (
                  <p className="no-comments">아직 댓글이 없습니다.</p>
                )}
              </div>
            </div>
          )}
        {/* 유사 여행 추천 */}
        {similarPosts.length > 0 && (
          <div className="similar-trips-section">
            <h4 className="similar-trips-title">비슷한 여행 기록</h4>
            <div className="similar-trips-grid">
              {similarPosts.map((p) => (
                <div
                  key={p.id}
                  className="similar-trip-card"
                  onClick={() => navigate(`/trip/${p.id}`)}
                >
                  <div className="similar-trip-thumb">
                    {p.thumbnail_url
                      ? <img src={p.thumbnail_url} alt={p.title} />
                      : <span className="similar-trip-icon">✈️</span>
                    }
                  </div>
                  <div className="similar-trip-body">
                    <p className="similar-trip-title">{p.title}</p>
                    {p.tags?.length > 0 && (
                      <div className="similar-trip-tags">
                        {p.tags.slice(0, 3).map(t => (
                          <span key={t} className="similar-trip-tag">#{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        </div>
      </div>
    </div>
  );
};

export default TripDetailPage;
