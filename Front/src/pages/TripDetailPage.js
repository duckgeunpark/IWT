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

  useEffect(() => {
    if (showComments) {
      dispatch(fetchComments({ postId }));
    }
  }, [showComments, postId, dispatch]);

  useEffect(() => {
    if (!mapRef.current || !GOOGLE_MAPS_KEY) return;
    if (mapInstanceRef.current) return;

    const gpsPhotos = photos.filter(p => p.location?.lat && p.location?.lng);
    if (gpsPhotos.length === 0) return;

    const initMap = () => {
      const center = { lat: gpsPhotos[0].location.lat, lng: gpsPhotos[0].location.lng };
      const map = new window.google.maps.Map(mapRef.current, {
        center,
        zoom: 10,
        mapTypeId: 'roadmap',
      });
      mapInstanceRef.current = map;

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

  const handleShare = useCallback(() => {
    const url = window.location.href;
    if (navigator.share) {
      navigator.share({ title: trip?.title || '여행 기록', url });
    } else {
      navigator.clipboard.writeText(url).then(() => alert('링크가 복사됐습니다!'));
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
  const isFollowing = followStatus[trip.user_id]?.following || false;
  const tags = Array.isArray(trip.tags) ? trip.tags : [];
  const activePhoto = photos[activePhotoIndex];
  const gpsPhotos = photos.filter(p => p.location?.lat && p.location?.lng);

  return (
    <div className="trip-detail-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      {/* ── 히어로 캐러셀 (전체너비) ── */}
      <div className="trip-hero">
        {photos.length > 0 ? (
          <>
            <img
              src={activePhoto?.url}
              alt={activePhoto?.file_name || '여행 사진'}
              className="trip-hero-img"
            />
            {photos.length > 1 && (
              <>
                <button
                  className="hero-nav hero-nav-prev"
                  onClick={() => setActivePhotoIndex(i => (i - 1 + photos.length) % photos.length)}
                >‹</button>
                <button
                  className="hero-nav hero-nav-next"
                  onClick={() => setActivePhotoIndex(i => (i + 1) % photos.length)}
                >›</button>
                <div className="hero-counter">{activePhotoIndex + 1} / {photos.length}</div>
              </>
            )}
          </>
        ) : (
          <div className="trip-hero-empty blue-gradient">
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

      {/* ── 메타바 (전체너비) ── */}
      <div className="trip-meta-bar">
        <div className="trip-meta-inner">
          <div className="trip-meta-top-row">
            <div
              className="trip-author"
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

            <div className="trip-meta-actions">
              <div className="trip-actions">
                <div className="trip-actions-left">
                  <button className={`action-icon-btn ${isLiked ? 'liked' : ''}`} onClick={handleLike}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill={isLiked ? '#ed4956' : 'none'} stroke={isLiked ? '#ed4956' : 'currentColor'} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                    </svg>
                  </button>
                  <button className="action-icon-btn" onClick={() => setShowComments(v => !v)}>
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

          <h1 className="trip-title">{trip.title}</h1>
          <div className="trip-meta">
            <span className="trip-meta-item">{formatDate(trip.created_at)}</span>
            <span className="trip-meta-divider">&middot;</span>
            <span className="trip-meta-item">사진 {trip.photo_count || 0}장</span>
          </div>
          {likesCount > 0 && (
            <div className="trip-likes">
              <strong>{likesCount}</strong>명이 좋아합니다
            </div>
          )}
          {tags.length > 0 && (
            <div className="trip-tags">
              {tags.map((tag) => (
                <span key={tag} className="trip-tag">#{tag}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── 본문 + 사이드바 ── */}
      <div className="trip-body">
        <div className="trip-content">
          {trip.description ? (
            <MarkdownPreview content={trip.description} />
          ) : (
            <p className="trip-no-content">내용이 없습니다.</p>
          )}
        </div>

        <aside className="trip-sidebar">
          {gpsPhotos.length > 0 && (
            <div className="sidebar-map" ref={mapRef} />
          )}
          {photos.length > 1 && (
            <div className="sidebar-photo-section">
              <p className="sidebar-section-label">사진 {photos.length}장</p>
              <div className="sidebar-photo-grid">
                {photos.map((photo, i) => (
                  <img
                    key={photo.id}
                    src={photo.url}
                    alt=""
                    onClick={() => setActivePhotoIndex(i)}
                    className={`sidebar-photo-thumb${i === activePhotoIndex ? ' active' : ''}`}
                  />
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>

      {/* ── 댓글 (전체너비) ── */}
      {showComments && (
        <div className="trip-comments-outer">
          <div className="trip-comments-inner">
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
        </div>
      )}

      {/* ── 비슷한 여행 (전체너비) ── */}
      {similarPosts.length > 0 && (
        <div className="similar-trips-outer">
          <div className="similar-trips-inner">
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
        </div>
      )}
    </div>
  );
};

export default TripDetailPage;
