import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { parseDate } from '../utils/dateUtils';
import Header from '../components/Header';
import { apiClient } from '../services/apiClient';
import useDisplayName from '../hooks/useDisplayName';
import '../styles/MainPage.css';

// 그라디언트 팔레트 (썸네일 없을 때)
const GRADIENTS = [
  'linear-gradient(135deg,#667eea,#764ba2)',
  'linear-gradient(135deg,#f093fb,#f5576c)',
  'linear-gradient(135deg,#4facfe,#00f2fe)',
  'linear-gradient(135deg,#43e97b,#38f9d7)',
  'linear-gradient(135deg,#fa709a,#fee140)',
  'linear-gradient(135deg,#a18cd1,#fbc2eb)',
  'linear-gradient(135deg,#ffecd2,#fcb69f)',
  'linear-gradient(135deg,#a1c4fd,#c2e9fb)',
];

function formatDate(isoString) {
  if (!isoString) return '';
  const d = parseDate(isoString);
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}.${String(d.getDate()).padStart(2, '0')}`;
}

// ── 내 여행 컴팩트 카드 ──
const MyTripCard = ({ post, onClick, onDelete, index }) => {
  const gradient = GRADIENTS[index % GRADIENTS.length];
  const isDraft = post.status === 'draft';

  const handleDelete = (e) => {
    e.stopPropagation();
    if (!window.confirm('임시저장을 삭제할까요?')) return;
    onDelete(post.id);
  };

  return (
    <div
      className={`my-trip-card${isDraft ? ' my-trip-card--draft' : ''}`}
      onClick={onClick}
    >
      {isDraft && <span className="my-trip-draft-badge">임시저장</span>}
      {isDraft && (
        <button className="my-trip-delete-btn" onClick={handleDelete} title="삭제">×</button>
      )}
      <div className="my-trip-thumb" style={{ background: gradient }}>
        {post.thumbnail_url && (
          <img src={post.thumbnail_url} alt={post.title} className="my-trip-thumb-img" />
        )}
      </div>
      <div className="my-trip-info">
        <p className="my-trip-title">{post.title}</p>
        <p className="my-trip-date">{formatDate(post.created_at)}</p>
        {post.photo_count > 0 && (
          <p className="my-trip-count">사진 {post.photo_count}장</p>
        )}
      </div>
    </div>
  );
};

// ── 탐색 그리드 카드 ──
const DiscoverCard = ({ post, onClick, index }) => {
  const gradient = GRADIENTS[index % GRADIENTS.length];
  const authorName = post.author?.name || (post.user_id || '').split('|').pop()?.slice(0, 10);
  const authorInitial = authorName?.[0]?.toUpperCase() || '?';

  return (
    <div className="discover-card" onClick={onClick}>
      <div className="discover-card-thumb" style={{ background: gradient }}>
        {post.thumbnail_url ? (
          <img src={post.thumbnail_url} alt={post.title} className="discover-thumb-img" />
        ) : (
          <span className="discover-thumb-icon">✈️</span>
        )}
        {post.photo_count > 0 && (
          <span className="discover-thumb-count">📷 {post.photo_count}</span>
        )}
      </div>
      <div className="discover-card-body">
        <h3 className="discover-card-title">{post.title}</h3>
        {post.description && (
          <p className="discover-card-desc">
            {post.description.replace(/[#*`>]/g, '').slice(0, 60)}
            {post.description.length > 60 ? '…' : ''}
          </p>
        )}
        <div className="discover-card-footer">
          <div className="discover-author">
            {post.author?.picture ? (
              <img src={post.author.picture} alt="" className="discover-avatar-img" />
            ) : (
              <div className="discover-avatar-default">{authorInitial}</div>
            )}
            <span className="discover-author-name">{authorName}</span>
          </div>
          {post.likes_count > 0 && (
            <span className="discover-likes">♥ {post.likes_count}</span>
          )}
        </div>
      </div>
    </div>
  );
};

// ── 메인 페이지 ──
const MainPage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: authLoading, loginWithRedirect, user } = useAuth0();
  const [myPosts, setMyPosts] = useState([]);
  const [publicPosts, setPublicPosts] = useState([]);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState(null);
  const displayName = useDisplayName();

  const handleDeleteDraft = async (postId) => {
    try {
      await apiClient.delete(`/api/v1/posts/${postId}`);
      setMyPosts(prev => prev.filter(p => p.id !== postId));
    } catch (err) {
      console.error('삭제 실패:', err);
      alert('삭제에 실패했습니다.');
    }
  };

  useEffect(() => {
    if (authLoading) return;

    const loadData = async () => {
      setDataLoading(true);
      setError(null);
      try {
        const publicRes = await apiClient.get('/api/v1/posts?skip=0&limit=12');
        const allPublic = publicRes?.posts || [];

        if (isAuthenticated && user?.sub) {
          const myRes = await apiClient.get(`/api/v1/posts/user/${encodeURIComponent(user.sub)}?skip=0&limit=6&include_drafts=true`);
          const myIds = new Set((myRes?.posts || []).map(p => p.id));
          setMyPosts(myRes?.posts || []);
          setPublicPosts(allPublic.filter(p => !myIds.has(p.id)));
        } else {
          setMyPosts([]);
          setPublicPosts(allPublic);
        }
      } catch (err) {
        console.error('게시글 로드 실패:', err);
        setError('게시글을 불러오는 데 실패했습니다.');
      } finally {
        setDataLoading(false);
      }
    };

    loadData();
  }, [authLoading, isAuthenticated, user]);

  if (authLoading) {
    return (
      <div className="main-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="main-content">
          <div className="page-loading">
            <div className="page-loading-spinner" />
            <p>로딩 중...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="main-content">
        {/* ── 인사말 (로그인 시) ── */}
        {isAuthenticated && (
          <div className="home-greeting">
            <h2 className="home-greeting-text">
              안녕하세요, {displayName}님
            </h2>
            <p className="home-greeting-sub">오늘도 새로운 여행을 기록해 보세요</p>
          </div>
        )}

        {/* ── 비로그인 웰컴 ── */}
        {!isAuthenticated && (
          <div className="home-welcome">
            <h2 className="home-welcome-title">I Want. I Went. Trip.</h2>
            <p className="home-welcome-sub">사진을 업로드하면 AI가 자동으로 여행 기록을 만들어드려요</p>
            <button className="home-welcome-cta" onClick={() => loginWithRedirect()}>
              시작하기
            </button>
          </div>
        )}

        {/* ── 내 여행 (수평 스크롤, 로그인 시) ── */}
        {isAuthenticated && (
          <section className="home-section">
            <div className="home-section-header">
              <h3 className="home-section-title">내 여행</h3>
              <button className="home-section-more" onClick={() => navigate('/profile')}>
                전체 보기
              </button>
            </div>
            {dataLoading ? (
              <div className="home-strip-loading">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="my-trip-card skeleton" />
                ))}
              </div>
            ) : myPosts.length === 0 ? (
              <div className="home-my-empty">
                <p>아직 기록한 여행이 없어요.</p>
                <button className="home-my-create-btn" onClick={() => navigate('/trip/new')}>
                  첫 여행 기록하기
                </button>
              </div>
            ) : (
              <div className="my-trips-strip">
                {myPosts.map((post, i) => (
                  <MyTripCard
                    key={post.id}
                    post={post}
                    index={i}
                    onClick={() => navigate(post.status === 'draft' ? `/trip/${post.id}/edit` : `/trip/${post.id}`)}
                    onDelete={handleDeleteDraft}
                  />
                ))}
              </div>
            )}
          </section>
        )}

        {/* ── 발견하기 그리드 ── */}
        <section className="home-section">
          <div className="home-section-header">
            <h3 className="home-section-title">
              {isAuthenticated ? '이런 여행 어때요?' : '인기 여행 기록'}
            </h3>
            <button className="home-section-more" onClick={() => navigate('/explore')}>
              탐색 더 보기
            </button>
          </div>

          {error && (
            <p className="home-error">{error}</p>
          )}

          {dataLoading ? (
            <div className="discover-grid">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="discover-card skeleton" />
              ))}
            </div>
          ) : publicPosts.length === 0 ? (
            <div className="home-discover-empty">
              <p>아직 공개된 여행이 없어요.</p>
            </div>
          ) : (
            <div className="discover-grid">
              {publicPosts.slice(0, 9).map((post, i) => (
                <DiscoverCard
                  key={post.id}
                  post={post}
                  index={i}
                  onClick={() => navigate(`/trip/${post.id}`)}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default MainPage;
