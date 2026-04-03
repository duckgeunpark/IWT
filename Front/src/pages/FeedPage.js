import React, { useEffect, useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { useDispatch, useSelector } from 'react-redux';
import Header from '../components/Header';
import { fetchFeed, toggleLike, toggleBookmark } from '../store/socialSlice';
import '../styles/FeedPage.css';

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

  if (!isAuthenticated) {
    return (
      <div className="feed-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="feed-login-prompt">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <h2>팔로우한 사람들의 여행</h2>
          <p>로그인하고 다른 여행자를 팔로우하면 피드에서 새 게시글을 확인할 수 있어요.</p>
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
        <h2 className="feed-title">피드</h2>

        {isLoading && feed.posts.length === 0 ? (
          <div className="feed-loading">
            <div className="page-loading-spinner" />
            <p>피드를 불러오는 중...</p>
          </div>
        ) : feed.posts.length === 0 ? (
          <div className="feed-empty">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="10" />
              <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
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
              {feed.posts.map((post) => (
                <article
                  key={post.id}
                  className="feed-card"
                  onClick={() => navigate(`/trip/${post.id}`)}
                >
                  {/* Card Header - Author */}
                  <div className="feed-card-header">
                    <div className="feed-author">
                      <div className="feed-author-avatar">
                        {post.author?.picture ? (
                          <img src={post.author.picture} alt="" />
                        ) : (
                          <div className="feed-avatar-default">
                            {(post.author?.name || post.user_id || '?')[0].toUpperCase()}
                          </div>
                        )}
                      </div>
                      <div className="feed-author-info">
                        <span className="feed-author-name">{post.author?.name || post.user_id}</span>
                        <span className="feed-post-date">
                          {new Date(post.created_at).toLocaleDateString('ko-KR')}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="feed-card-body">
                    <h3 className="feed-card-title">{post.title}</h3>
                    {post.description && (
                      <p className="feed-card-desc">
                        {post.description.slice(0, 150)}{post.description.length > 150 ? '...' : ''}
                      </p>
                    )}
                    {post.tags && Array.isArray(post.tags) && post.tags.length > 0 && (
                      <div className="feed-card-tags">
                        {post.tags.slice(0, 5).map((tag) => (
                          <span key={tag} className="feed-tag">#{tag}</span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Card Footer - Actions */}
                  <div className="feed-card-footer">
                    <div className="feed-actions-left">
                      <button
                        className={`feed-action-btn ${post.is_liked ? 'liked' : ''}`}
                        onClick={(e) => handleLike(e, post.id)}
                      >
                        <svg width="20" height="20" viewBox="0 0 24 24" fill={post.is_liked ? '#ed4956' : 'none'} stroke={post.is_liked ? '#ed4956' : 'currentColor'} strokeWidth="2">
                          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                        </svg>
                        {post.likes_count > 0 && <span>{post.likes_count}</span>}
                      </button>
                      <button className="feed-action-btn">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                        </svg>
                        {post.comments_count > 0 && <span>{post.comments_count}</span>}
                      </button>
                      <span className="feed-photo-count">{post.photo_count}장</span>
                    </div>
                    <button
                      className={`feed-action-btn ${post.is_bookmarked ? 'saved' : ''}`}
                      onClick={(e) => handleBookmark(e, post.id)}
                    >
                      <svg width="20" height="20" viewBox="0 0 24 24" fill={post.is_bookmarked ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2">
                        <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
                      </svg>
                    </button>
                  </div>
                </article>
              ))}
            </div>

            {/* Pagination */}
            {feed.total > limit && (
              <div className="feed-pagination">
                <button
                  className="feed-page-btn"
                  disabled={page === 0}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                >
                  이전
                </button>
                <span className="feed-page-info">
                  {page + 1} / {Math.ceil(feed.total / limit)}
                </span>
                <button
                  className="feed-page-btn"
                  disabled={(page + 1) * limit >= feed.total}
                  onClick={() => setPage((p) => p + 1)}
                >
                  다음
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
