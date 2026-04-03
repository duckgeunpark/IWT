import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/apiClient';
import Header from '../components/Header';
import '../styles/ExplorePage.css';

const SEASONS = ['전체', '봄', '여름', '가을', '겨울'];
const DIFFICULTIES = ['전체', '쉬움', '보통', '어려움'];
const SORT_OPTIONS = [
  { value: 'newest', label: '최신순' },
  { value: 'popular', label: '인기순' },
  { value: 'most_liked', label: '좋아요순' },
];

const ExplorePage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [regionFilter, setRegionFilter] = useState('');
  const [themeFilter, setThemeFilter] = useState('');
  const [selectedSeason, setSelectedSeason] = useState('전체');
  const [selectedDifficulty, setSelectedDifficulty] = useState('전체');
  const [sortBy, setSortBy] = useState('newest');
  const [showAIOnly, setShowAIOnly] = useState(false);

  // API 데이터
  const [posts, setPosts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState({ regions: [], tags: [] });
  const [showSuggestions, setShowSuggestions] = useState(false);

  // 검색 API 호출
  const searchPosts = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (regionFilter) params.append('region', regionFilter);
      if (themeFilter) params.append('theme', themeFilter);
      params.append('sort', sortBy);
      params.append('limit', '20');

      const data = await apiClient.get(`/api/v1/search/posts?${params.toString()}`);
      setPosts(data.posts || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('검색 실패:', err);
      setPosts([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, regionFilter, themeFilter, sortBy]);

  // 검색어 변경 시 자동 검색
  useEffect(() => {
    const timer = setTimeout(() => {
      searchPosts();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchPosts]);

  // 자동완성
  useEffect(() => {
    if (searchQuery.length < 1) {
      setSuggestions({ regions: [], tags: [] });
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const data = await apiClient.get(`/api/v1/search/suggestions?q=${encodeURIComponent(searchQuery)}`);
        setSuggestions(data);
      } catch {
        setSuggestions({ regions: [], tags: [] });
      }
    }, 200);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSuggestionClick = (value, type) => {
    if (type === 'region') {
      setRegionFilter(value);
      setSearchQuery('');
    } else {
      setSearchQuery(value);
    }
    setShowSuggestions(false);
  };

  const hasSuggestions = suggestions.regions.length > 0 || suggestions.tags.length > 0;

  return (
    <div className="explore-page">
      <Header toggleTheme={toggleTheme} theme={theme} />

      <div className="explore-content">
        {/* Hero */}
        <div className="explore-hero">
          <div className="explore-hero-inner">
            <h1 className="explore-title">
              <span className="gradient-text">AI</span>가 추천하는 여행 경로
            </h1>
            <p className="explore-subtitle">
              커뮤니티의 실제 여행 데이터와 AI 분석을 기반으로 최적의 경로를 추천합니다
            </p>
          </div>
        </div>

        {/* Search & Filter */}
        <section className="explore-section">
          <div className="explore-search-bar">
            <div className="explore-search-input-wrapper">
              <svg className="explore-search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              <input
                type="text"
                className="explore-search-input"
                placeholder="도시, 나라, 태그로 검색..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
              />
              {searchQuery && (
                <button className="explore-search-clear" onClick={() => setSearchQuery('')}>
                  &times;
                </button>
              )}

              {/* 자동완성 */}
              {showSuggestions && hasSuggestions && (
                <div className="search-suggestions">
                  {suggestions.regions.length > 0 && (
                    <div className="suggestion-group">
                      <span className="suggestion-label">지역</span>
                      {suggestions.regions.map((r) => (
                        <button key={r} className="suggestion-item" onMouseDown={() => handleSuggestionClick(r, 'region')}>
                          {r}
                        </button>
                      ))}
                    </div>
                  )}
                  {suggestions.tags.length > 0 && (
                    <div className="suggestion-group">
                      <span className="suggestion-label">태그</span>
                      {suggestions.tags.map((t) => (
                        <button key={t} className="suggestion-item" onMouseDown={() => handleSuggestionClick(t, 'tag')}>
                          #{t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* 필터 칩 */}
          <div className="explore-filters">
            <div className="filter-group">
              <span className="filter-label">지역</span>
              <input
                type="text"
                className="filter-text-input"
                placeholder="지역명 입력 (예: 부산, 제주, 도쿄)"
                value={regionFilter}
                onChange={(e) => setRegionFilter(e.target.value)}
              />
              {regionFilter && (
                <button className="filter-clear-btn" onClick={() => setRegionFilter('')}>&times;</button>
              )}
            </div>

            <div className="filter-group">
              <span className="filter-label">테마</span>
              <input
                type="text"
                className="filter-text-input"
                placeholder="테마 입력 (예: 맛집, 자연, 문화)"
                value={themeFilter}
                onChange={(e) => setThemeFilter(e.target.value)}
              />
              {themeFilter && (
                <button className="filter-clear-btn" onClick={() => setThemeFilter('')}>&times;</button>
              )}
            </div>

            <div className="filter-row">
              <select
                className="sort-select"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
              >
                {SORT_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Active Filters */}
          {(regionFilter || themeFilter || searchQuery) && (
            <div className="active-filters">
              {searchQuery && (
                <span className="active-filter-chip">
                  검색: {searchQuery}
                  <button onClick={() => setSearchQuery('')}>&times;</button>
                </span>
              )}
              {regionFilter && (
                <span className="active-filter-chip">
                  지역: {regionFilter}
                  <button onClick={() => setRegionFilter('')}>&times;</button>
                </span>
              )}
              {themeFilter && (
                <span className="active-filter-chip">
                  테마: {themeFilter}
                  <button onClick={() => setThemeFilter('')}>&times;</button>
                </span>
              )}
              <button
                className="explore-reset-btn"
                onClick={() => {
                  setSearchQuery('');
                  setRegionFilter('');
                  setThemeFilter('');
                  setSortBy('newest');
                }}
              >
                전체 초기화
              </button>
            </div>
          )}
        </section>

        {/* Route List */}
        <section className="explore-section">
          <div className="section-header-row">
            <h2 className="explore-section-title">
              검색 결과 <span className="route-count">{total}</span>
            </h2>
          </div>

          {loading ? (
            <div className="explore-loading">
              <div className="page-loading-spinner" />
              <p>검색 중...</p>
            </div>
          ) : posts.length === 0 ? (
            <div className="explore-empty">
              <p>검색 결과가 없습니다.</p>
              <button className="explore-reset-btn" onClick={() => {
                setSearchQuery('');
                setRegionFilter('');
                setThemeFilter('');
              }}>
                필터 초기화
              </button>
            </div>
          ) : (
            <div className="route-grid">
              {posts.map((post) => (
                <div
                  key={post.id}
                  className="route-card"
                  onClick={() => navigate(`/trip/${post.id}`)}
                >
                  {/* Card Header */}
                  <div className="route-card-header blue-gradient">
                    <div className="route-card-overlay">
                      {post.locations && post.locations.length > 0 && (
                        <div className="route-card-stops">
                          {post.locations.slice(0, 3).map((loc, j) => (
                            <React.Fragment key={j}>
                              <span>{loc.city || loc.country || '위치'}</span>
                              {j < Math.min(post.locations.length, 3) - 1 && <span className="stop-arrow-sm">→</span>}
                            </React.Fragment>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="route-card-body">
                    <h3 className="route-card-title">{post.title}</h3>
                    <p className="route-card-desc">
                      {post.description ? post.description.slice(0, 100) + (post.description.length > 100 ? '...' : '') : ''}
                    </p>

                    <div className="route-card-meta">
                      <span className="route-meta-item">{post.photo_count}장</span>
                      {post.likes_count > 0 && (
                        <span className="route-meta-item">♥ {post.likes_count}</span>
                      )}
                      <span className="route-meta-item">
                        {new Date(post.created_at).toLocaleDateString('ko-KR')}
                      </span>
                    </div>

                    {/* Categories */}
                    {post.categories && Object.keys(post.categories).length > 0 && (
                      <div className="route-card-tags">
                        {Object.values(post.categories).flat().slice(0, 4).map(cat => (
                          <span key={cat} className="route-tag">#{cat}</span>
                        ))}
                      </div>
                    )}

                    {/* Tags */}
                    {post.tags && (
                      <div className="route-card-tags">
                        {(Array.isArray(post.tags) ? post.tags : []).slice(0, 3).map(tag => (
                          <span key={tag} className="route-tag">#{tag}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

export default ExplorePage;
