import React, { useEffect, useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { useDispatch, useSelector } from 'react-redux';
import Header from '../components/Header';
import { fetchFeed, toggleLike, toggleBookmark } from '../store/socialSlice';
import { formatRelativeTime } from '../utils/dateUtils';
import '../styles/FeedPage.css';

const GRADIENTS = [
  'linear-gradient(135deg,#667eea,#764ba2)',
  'linear-gradient(135deg,#f093fb,#f5576c)',
  'linear-gradient(135deg,#4facfe,#00f2fe)',
  'linear-gradient(135deg,#43e97b,#38f9d7)',
  'linear-gradient(135deg,#fa709a,#fee140)',
  'linear-gradient(135deg,#a18cd1,#fbc2eb)',
];

const relativeTime = (iso) => formatRelativeTime(iso);

const parseTags = (tags) => {
  if (Array.isArray(tags)) return tags;
  if (typeof tags === 'string') {
    try { return JSON.parse(tags); } catch { return []; }
  }
  return [];
};

// ── 피드 카드 ──
const FeedCard = ({ post, onLike, onBookmark, index }) => {
  const navigate = useNavigate();
  const gradient = GRADIENTS[index % GRADIENTS.length];
  const tags = parseTags(post.tags);
  const authorName = post.author?.name || (post.user_id || '').split('|').pop()?.slice(0, 14) || '?';
  const authorInitial = authorName[0]?.toUpperCase() || '?';
  const description = post.description?.replace(/[#*`>_~\[\]]/g, '').trim() || '';

  return (
    <article className="feed-card" onClick={() => navigate(`/trip/${post.id}`)}>
      {/* ── 썸네일 ── */}
      <div className="feed-card-thumb" style={{ background: gradient }}>
        {post.thumbnail_url ? (
          <img src={post.thumbnail_url} alt={post.title} className="feed-thumb-img" />
        ) : (
          <span className="feed-thumb-icon">✈️</span>
        )}
        {post.photo_count > 0 && (
          <span className="feed-thumb-count">📷 {post.photo_count}</span>
        )}
      </div>

      {/* ── 본문 ── */}
      <div className="feed-card-body">
        {/* 작성자 + 시간 */}
        <div className="feed-author-row">
          <div className="feed-author">
            {post.author?.picture ? (
              <img src={post.author.picture} alt="" className="feed-avatar-img" />
            ) : (
              <div className="feed-avatar-default">{authorInitial}</div>
            )}
            <div className="feed-author-info">
              <span className="feed-author-name">{authorName}</span>
              <span className="feed-post-time">{relativeTime(post.created_at)}</span>
            </div>
          </div>
        </div>

        {/* 제목 */}
        <h3 className="feed-card-title">{post.title}</h3>

        {/* 설명 */}
        {description && (
          <p className="feed-card-desc">
            {description.slice(0, 120)}{description.length > 120 ? '…' : ''}
          </p>
        )}

        {/* 태그 */}
        {tags.length > 0 && (
          <div className="feed-card-tags">
            {tags.slice(0, 4).map(tag => (
              <span key={tag} className="feed-tag">#{tag}</span>
            ))}
          </div>
        )}

        {/* 액션 바 */}
        <div className="feed-actions">
          <div className="feed-actions-left">
            <button
              className={`feed-action-btn ${post.is_liked ? 'liked' : ''}`}
              onClick={(e) => { e.stopPropagation(); onLike(e, post.id); }}
            >
              <svg width="19" height="19" viewBox="0 0 24 24"
                fill={post.is_liked ? '#ed4956' : 'none'}
                stroke={post.is_liked ? '#ed4956' : 'currentColor'}
                strokeWidth="2">
                <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
              </svg>
              {post.likes_count > 0 && <span>{post.likes_count}</span>}
            </button>

            <button
              className="feed-action-btn"
              onClick={(e) => { e.stopPropagation(); navigate(`/trip/${post.id}`); }}
            >
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              {post.comments_count > 0 && <span>{post.comments_count}</span>}
            </button>
          </div>

          <button
            className={`feed-action-btn bookmark ${post.is_bookmarked ? 'saved' : ''}`}
            onClick={(e) => { e.stopPropagation(); onBookmark(e, post.id); }}
          >
            <svg width="19" height="19" viewBox="0 0 24 24"
              fill={post.is_bookmarked ? 'currentColor' : 'none'}
              stroke="currentColor"
              strokeWidth="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
          </button>
        </div>
      </div>
    </article>
  );
};

// ── 피드 페이지 ──
const FeedPage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { isAuthenticated, loginWithRedirect } = useAuth0();
  const { feed, isLoading } = useSelector((state) => state.social);
  const [page, setPage] = useState(0);
  const limit = 10;

  useEffect(() => {
    if (isAuthenticated) {
      dispatch(fetchFeed({ skip: page * limit, limit }));
    }
  }, [dispatch, isAuthenticated, page]);

  const handleLike = useCallback((e, postId) => {
    e.stopPropagation();
    dispatch(toggleLike(postId));
  }, [dispatch]);

  const handleBookmark = useCallback((e, postId) => {
    e.stopPropagation();
    dispatch(toggleBookmark(postId));
  }, [dispatch]);

  /* ── 비로그인 ── */
  if (!isAuthenticated) {
    return (
      <div className="feed-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="feed-login-prompt">
          <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <h2>팔로잉 피드</h2>
          <p>로그인하고 다른 여행자를 팔로우하면<br />새 게시글을 여기서 확인할 수 있어요.</p>
          <button className="feed-login-btn" onClick={() => loginWithRedirect()}>
            로그인
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="feed-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="feed-content">
        <div className="feed-header">
          <h2 className="feed-title">팔로잉</h2>
          <p className="feed-subtitle">내가 팔로우한 여행자의 새 기록</p>
        </div>

        {isLoading && feed.posts.length === 0 ? (
          <div className="feed-loading">
            <div className="feed-loading-spinner" />
            <p>불러오는 중...</p>
          </div>
        ) : feed.posts.length === 0 ? (
          <div className="feed-empty">
            <svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4l3 3" />
            </svg>
            <h3>아직 피드가 비어있어요</h3>
            <p>다른 여행자를 팔로우하면 새 게시글이 여기에 표시됩니다.</p>
            <button className="feed-explore-btn" onClick={() => navigate('/explore')}>
              여행 탐색하기
            </button>
          </div>
        ) : (
          <>
            <div className="feed-list">
              {feed.posts.map((post, i) => (
                <FeedCard
                  key={post.id}
                  post={post}
                  index={i}
                  onLike={handleLike}
                  onBookmark={handleBookmark}
                />
              ))}
            </div>

            {/* 더 불러오기 */}
            {feed.total > (page + 1) * limit && (
              <div className="feed-load-more">
                <button
                  className="feed-load-more-btn"
                  disabled={isLoading}
                  onClick={() => setPage(p => p + 1)}
                >
                  {isLoading ? '불러오는 중...' : '더 보기'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default FeedPage;
