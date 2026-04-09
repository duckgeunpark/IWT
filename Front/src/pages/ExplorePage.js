import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import Header from '../components/Header';
import { formatRelativeTime } from '../utils/dateUtils';
import '../styles/ExplorePage.css';

// ── 지역/테마 키워드 (스마트 감지용) ──
const KNOWN_REGIONS = [
  '서울', '부산', '제주', '인천', '광주', '대구', '대전', '수원', '경주', '강릉',
  '속초', '여수', '전주', '춘천', '포항', '울산', '목포', '통영', '거제',
  '도쿄', '오사카', '교토', '삿포로', '후쿠오카', '나고야', '요코하마',
  '방콕', '치앙마이', '파타야', '푸켓',
  '파리', '런던', '바르셀로나', '로마', '암스테르담',
  '뉴욕', 'LA', '라스베이거스', '시카고', '샌프란시스코',
  '홍콩', '싱가포르', '발리', '타이페이', '베이징', '상하이',
  '시드니', '멜버른', '두바이', '이스탄불',
];
const KNOWN_THEMES = [
  '맛집', '카페', '자연', '문화', '쇼핑', '액티비티', '힐링', '야경', '축제',
  '해수욕', '등산', '드라이브', '트레킹', '스키', '골프', '캠핑',
  '가족', '커플', '혼행', '친구', '단체',
  '포토존', '인스타', '한옥', '온천', '스파',
];

const SORT_OPTIONS = [
  { value: 'newest', label: '최신순' },
  { value: 'popular', label: '인기순' },
  { value: 'most_liked', label: '좋아요순' },
];

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

// ── 콤마 구분 토큰 분류 ──
const classifyToken = (token) => {
  const t = token.trim().toLowerCase();
  if (KNOWN_REGIONS.some(r => r.toLowerCase().includes(t) || t.includes(r.toLowerCase()))) {
    return { type: 'region', value: token.trim() };
  }
  if (KNOWN_THEMES.some(th => th.toLowerCase().includes(t) || t.includes(th.toLowerCase()))) {
    return { type: 'theme', value: token.trim() };
  }
  return { type: 'keyword', value: token.trim() };
};

const parseSearchInput = (input) => {
  const tokens = input.split(',').map(t => t.trim()).filter(Boolean);
  const result = { regions: [], themes: [], keywords: [] };
  tokens.forEach(token => {
    const classified = classifyToken(token);
    result[classified.type === 'region' ? 'regions' : classified.type === 'theme' ? 'themes' : 'keywords'].push(classified.value);
  });
  return result;
};

// ── 상대 시간 ──
const relativeTime = (iso) => formatRelativeTime(iso);

// ── 탐색 카드 ──
const ExploreCard = ({ post, onClick, index }) => {
  const gradient = GRADIENTS[index % GRADIENTS.length];
  const tags = Array.isArray(post.tags) ? post.tags : [];
  const authorName = post.author?.name || (post.user_id || '').split('|').pop()?.slice(0, 10);
  const authorInitial = authorName?.[0]?.toUpperCase() || '?';

  return (
    <div className="ex-card" onClick={onClick}>
      {/* 썸네일 */}
      <div className="ex-card-thumb" style={{ background: gradient }}>
        {post.thumbnail_url ? (
          <img src={post.thumbnail_url} alt={post.title} className="ex-thumb-img" />
        ) : (
          <span className="ex-thumb-icon">✈️</span>
        )}
        <div className="ex-thumb-overlay">
          {post.photo_count > 0 && (
            <span className="ex-thumb-count">📷 {post.photo_count}</span>
          )}
          {post.likes_count > 0 && (
            <span className="ex-thumb-likes">♥ {post.likes_count}</span>
          )}
        </div>
      </div>

      {/* 본문 */}
      <div className="ex-card-body">
        <h3 className="ex-card-title">{post.title}</h3>
        {post.description && (
          <p className="ex-card-desc">
            {post.description.replace(/[#*`>]/g, '').slice(0, 70)}
            {post.description.length > 70 ? '…' : ''}
          </p>
        )}
        {tags.length > 0 && (
          <div className="ex-card-tags">
            {tags.slice(0, 3).map(tag => (
              <span key={tag} className="ex-tag">#{tag}</span>
            ))}
          </div>
        )}
        <div className="ex-card-footer">
          <div className="ex-author">
            {post.author?.picture ? (
              <img src={post.author.picture} alt="" className="ex-avatar-img" />
            ) : (
              <div className="ex-avatar-default">{authorInitial}</div>
            )}
            <span className="ex-author-name">{authorName}</span>
          </div>
          <span className="ex-card-time">{relativeTime(post.created_at)}</span>
        </div>
      </div>
    </div>
  );
};

// ── 탐색 페이지 ──
const ExplorePage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
  const [parsedFilters, setParsedFilters] = useState({ regions: [], themes: [], keywords: [] });
  const [sortBy, setSortBy] = useState('newest');
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState({ regions: [], tags: [] });
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [semanticMode, setSemanticMode] = useState(false);
  const [expandedKeywords, setExpandedKeywords] = useState([]);
  const inputRef = useRef(null);

  // 검색어 파싱
  useEffect(() => {
    const parsed = parseSearchInput(searchInput);
    setParsedFilters(parsed);
  }, [searchInput]);

  // API 검색
  const searchPosts = useCallback(async () => {
    setLoading(true);
    setExpandedKeywords([]);
    try {
      // 의미 검색 모드: LLM 키워드 확장
      if (semanticMode && searchInput.trim()) {
        const data = await apiClient.get(
          `/api/v1/search/semantic?q=${encodeURIComponent(searchInput.trim())}&limit=24`
        );
        setPosts(data.posts || []);
        setExpandedKeywords(data.expanded_keywords || []);
        return;
      }

      // 일반 검색 모드
      const params = new URLSearchParams();
      if (parsedFilters.keywords.length) params.append('q', parsedFilters.keywords.join(' '));
      if (parsedFilters.regions.length) params.append('region', parsedFilters.regions[0]);
      if (parsedFilters.themes.length) params.append('theme', parsedFilters.themes[0]);
      params.append('sort', sortBy);
      params.append('limit', '24');

      const data = await apiClient.get(`/api/v1/search/posts?${params.toString()}`);
      setPosts(data.posts || []);
    } catch {
      // fallback: 공개 게시글 전체
      try {
        const data = await apiClient.get(`/api/v1/posts?skip=0&limit=24`);
        setPosts(data.posts || []);
      } catch {
        setPosts([]);
      }
    } finally {
      setLoading(false);
    }
  }, [parsedFilters, sortBy, semanticMode, searchInput]);

  useEffect(() => {
    const timer = setTimeout(searchPosts, 300);
    return () => clearTimeout(timer);
  }, [searchPosts]);

  // 자동완성
  useEffect(() => {
    if (searchInput.length < 1) {
      setSuggestions({ regions: [], tags: [] });
      return;
    }
    const lastToken = searchInput.split(',').pop().trim();
    if (!lastToken) return;
    const timer = setTimeout(async () => {
      try {
        const data = await apiClient.get(`/api/v1/search/suggestions?q=${encodeURIComponent(lastToken)}`);
        setSuggestions(data);
      } catch {
        setSuggestions({ regions: [], tags: [] });
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const hasSuggestions = suggestions.regions.length > 0 || suggestions.tags.length > 0;

  const applySuggestion = (value) => {
    const parts = searchInput.split(',');
    parts[parts.length - 1] = value;
    setSearchInput(parts.join(', ') + ', ');
    setShowSuggestions(false);
    inputRef.current?.focus();
  };

  const removeFilter = (type, value) => {
    const parts = searchInput.split(',').map(t => t.trim()).filter(t => t && t !== value);
    setSearchInput(parts.join(', '));
  };

  const hasFilters = parsedFilters.regions.length || parsedFilters.themes.length || parsedFilters.keywords.length;

  const activeChips = [
    ...parsedFilters.regions.map(v => ({ type: 'region', value: v, label: `📍 ${v}` })),
    ...parsedFilters.themes.map(v => ({ type: 'theme', value: v, label: `🏷 ${v}` })),
    ...parsedFilters.keywords.map(v => ({ type: 'keyword', value: v, label: `🔍 ${v}` })),
  ];

  return (
    <div className="explore-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="explore-content">
        {/* ── 헤더 행 ── */}
        <div className="explore-header-row">
          <h2 className="explore-page-title">여행 탐색</h2>
          <div className="explore-sort-chips">
            {SORT_OPTIONS.map(opt => (
              <button
                key={opt.value}
                className={`sort-chip ${sortBy === opt.value ? 'active' : ''}`}
                onClick={() => setSortBy(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── 스마트 검색창 ── */}
        <div className="explore-search-wrap">
          <div className="explore-smart-bar">
            <svg className="explore-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              ref={inputRef}
              type="text"
              className="explore-smart-input"
              placeholder={semanticMode ? 'AI 검색 — 예: 바다 보이는 카페, 일본 온천 여행' : '어디든, 무엇이든 — 예: 제주, 맛집, 힐링'}
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 180)}
            />
            <button
              className={`semantic-toggle-btn ${semanticMode ? 'active' : ''}`}
              onClick={() => { setSemanticMode(m => !m); setExpandedKeywords([]); }}
              title={semanticMode ? '일반 검색으로 전환' : 'AI 의미 검색으로 전환'}
            >
              {semanticMode ? '🤖 AI' : '🤖'}
            </button>
            {searchInput && (
              <button className="explore-clear-btn" onClick={() => setSearchInput('')}>×</button>
            )}

            {/* 자동완성 */}
            {showSuggestions && hasSuggestions && (
              <div className="explore-suggestions">
                {suggestions.regions.length > 0 && (
                  <div className="sugg-group">
                    <span className="sugg-label">📍 지역</span>
                    {suggestions.regions.map(r => (
                      <button key={r} className="sugg-item" onMouseDown={() => applySuggestion(r)}>{r}</button>
                    ))}
                  </div>
                )}
                {suggestions.tags.length > 0 && (
                  <div className="sugg-group">
                    <span className="sugg-label">🏷 태그</span>
                    {suggestions.tags.map(t => (
                      <button key={t} className="sugg-item" onMouseDown={() => applySuggestion(t)}>#{t}</button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 감지된 필터 힌트 */}
          {searchInput && (
            <p className="explore-parse-hint">
              {parsedFilters.regions.length > 0 && <span className="hint-chip region">📍 지역: {parsedFilters.regions.join(', ')}</span>}
              {parsedFilters.themes.length > 0 && <span className="hint-chip theme">🏷 테마: {parsedFilters.themes.join(', ')}</span>}
              {parsedFilters.keywords.length > 0 && <span className="hint-chip keyword">🔍 검색어: {parsedFilters.keywords.join(', ')}</span>}
            </p>
          )}
        </div>

        {/* ── 활성 필터 칩 ── */}
        {activeChips.length > 0 && (
          <div className="explore-active-chips">
            {activeChips.map(chip => (
              <span key={`${chip.type}-${chip.value}`} className="active-chip">
                {chip.label}
                <button className="active-chip-remove" onClick={() => removeFilter(chip.type, chip.value)}>×</button>
              </span>
            ))}
            <button className="reset-all-btn" onClick={() => setSearchInput('')}>전체 초기화</button>
          </div>
        )}

        {/* AI 확장 키워드 힌트 */}
        {semanticMode && expandedKeywords.length > 0 && (
          <div className="semantic-keywords-hint">
            <span className="semantic-hint-label">🤖 AI 확장 키워드:</span>
            {expandedKeywords.map(kw => (
              <span key={kw} className="semantic-kw-chip">{kw}</span>
            ))}
          </div>
        )}

        {/* ── 결과 카운트 ── */}
        <div className="explore-result-meta">
          {loading ? (
            <span className="result-meta-text">{semanticMode ? 'AI가 검색 중...' : '검색 중...'}</span>
          ) : (
            <span className="result-meta-text">
              {hasFilters && !semanticMode ? `필터 적용됨 · ` : ''}{posts.length}개 여행
            </span>
          )}
        </div>

        {/* ── 게시글 그리드 ── */}
        {loading ? (
          <div className="ex-grid">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="ex-card skeleton" />
            ))}
          </div>
        ) : posts.length === 0 ? (
          <div className="explore-empty">
            <p>검색 결과가 없어요.</p>
            <button className="reset-all-btn" onClick={() => setSearchInput('')}>필터 초기화</button>
          </div>
        ) : (
          <div className="ex-grid">
            {posts.map((post, idx) => (
              <ExploreCard
                key={post.id}
                post={post}
                index={idx}
                onClick={() => navigate(`/trip/${post.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ExplorePage;
