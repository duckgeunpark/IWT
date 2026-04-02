import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import Header from '../components/Header';
import '../styles/ExplorePage.css';

// 샘플 데이터 — 나중에 API로 대체
const SAMPLE_ROUTES = [
  {
    id: 101,
    title: '서울 → 부산 해안 드라이브',
    description: '동해안을 따라 달리는 3일간의 로드트립. 강릉 커피거리, 경주 불국사, 해운대를 지나는 최적 경로.',
    author: 'road_master',
    duration: '2박 3일',
    distance: '450km',
    season: '가을',
    difficulty: '쉬움',
    rating: 4.8,
    reviewCount: 234,
    usedCount: 1520,
    photoCount: 89,
    colorTheme: 'blue',
    tags: ['로드트립', '해안도로', '부산', '강릉'],
    stops: [
      { name: '서울', day: 1 },
      { name: '강릉', day: 1 },
      { name: '경주', day: 2 },
      { name: '부산', day: 3 },
    ],
    isAIRecommended: true,
    trendScore: 95,
  },
  {
    id: 102,
    title: '제주도 일주 완벽 코스',
    description: '4일 동안 제주도를 한 바퀴 도는 코스. 동쪽에서 서쪽으로, 관광지와 로컬 맛집을 균형 있게 배치.',
    author: 'jeju_lover',
    duration: '3박 4일',
    distance: '280km',
    season: '봄',
    difficulty: '쉬움',
    rating: 4.9,
    reviewCount: 567,
    usedCount: 3240,
    photoCount: 156,
    colorTheme: 'green',
    tags: ['제주', '일주', '맛집', '자연'],
    stops: [
      { name: '제주시', day: 1 },
      { name: '성산일출봉', day: 2 },
      { name: '서귀포', day: 3 },
      { name: '협재해변', day: 4 },
    ],
    isAIRecommended: true,
    trendScore: 98,
  },
  {
    id: 103,
    title: '교토 → 오사카 문화 탐방',
    description: '일본 간사이 지역의 전통과 현대를 모두 경험하는 코스. 사찰, 거리 음식, 야경까지.',
    author: 'japan_explorer',
    duration: '4박 5일',
    distance: '120km',
    season: '봄',
    difficulty: '보통',
    rating: 4.7,
    reviewCount: 189,
    usedCount: 890,
    photoCount: 210,
    colorTheme: 'purple',
    tags: ['일본', '교토', '오사카', '문화'],
    stops: [
      { name: '교토역', day: 1 },
      { name: '후시미이나리', day: 2 },
      { name: '나라', day: 3 },
      { name: '도톤보리', day: 4 },
      { name: '오사카성', day: 5 },
    ],
    isAIRecommended: false,
    trendScore: 82,
  },
  {
    id: 104,
    title: '방콕 먹방 투어 3일',
    description: '방콕의 길거리 음식부터 미쉐린 레스토랑까지, 위장이 허락하는 한 먹는 코스.',
    author: 'foodie_park',
    duration: '2박 3일',
    distance: '40km',
    season: '겨울',
    difficulty: '쉬움',
    rating: 4.6,
    reviewCount: 312,
    usedCount: 1890,
    photoCount: 178,
    colorTheme: 'yellow',
    tags: ['방콕', '태국', '먹방', '길거리음식'],
    stops: [
      { name: '카오산로드', day: 1 },
      { name: '짜뚜짝 시장', day: 2 },
      { name: '왓아룬', day: 3 },
    ],
    isAIRecommended: true,
    trendScore: 88,
  },
  {
    id: 105,
    title: '스위스 알프스 하이킹 루트',
    description: '융프라우에서 체르마트까지, 알프스의 절경을 걸으며 만끽하는 트레킹 코스.',
    author: 'alpine_hiker',
    duration: '6박 7일',
    distance: '180km',
    season: '여름',
    difficulty: '어려움',
    rating: 4.9,
    reviewCount: 98,
    usedCount: 340,
    photoCount: 320,
    colorTheme: 'blue',
    tags: ['스위스', '하이킹', '알프스', '트레킹'],
    stops: [
      { name: '인터라켄', day: 1 },
      { name: '그린델발트', day: 2 },
      { name: '융프라우요흐', day: 3 },
      { name: '라우터브루넨', day: 4 },
      { name: '체르마트', day: 6 },
    ],
    isAIRecommended: false,
    trendScore: 76,
  },
  {
    id: 106,
    title: '전주 한옥마을 당일치기',
    description: '전주 한옥마을에서 하루 동안 한복 체험, 비빔밥, 초코파이 맛집까지 알차게 즐기는 코스.',
    author: 'hanok_fan',
    duration: '당일',
    distance: '5km',
    season: '봄',
    difficulty: '쉬움',
    rating: 4.5,
    reviewCount: 456,
    usedCount: 5600,
    photoCount: 67,
    colorTheme: 'pink',
    tags: ['전주', '한옥마을', '당일치기', '한식'],
    stops: [
      { name: '전주 한옥마을 입구', day: 1 },
      { name: '경기전', day: 1 },
      { name: '전동성당', day: 1 },
      { name: '남부시장', day: 1 },
    ],
    isAIRecommended: true,
    trendScore: 91,
  },
];

const SEASONS = ['전체', '봄', '여름', '가을', '겨울'];
const DIFFICULTIES = ['전체', '쉬움', '보통', '어려움'];
const SORT_OPTIONS = [
  { value: 'trending', label: '인기순' },
  { value: 'rating', label: '평점순' },
  { value: 'newest', label: '최신순' },
  { value: 'most-used', label: '사용순' },
];

const ExplorePage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSeason, setSelectedSeason] = useState('전체');
  const [selectedDifficulty, setSelectedDifficulty] = useState('전체');
  const [sortBy, setSortBy] = useState('trending');
  const [showAIOnly, setShowAIOnly] = useState(false);

  const filteredRoutes = useMemo(() => {
    let routes = [...SAMPLE_ROUTES];

    // 검색어 필터
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      routes = routes.filter(r =>
        r.title.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.tags.some(t => t.toLowerCase().includes(q))
      );
    }

    // 시즌 필터
    if (selectedSeason !== '전체') {
      routes = routes.filter(r => r.season === selectedSeason);
    }

    // 난이도 필터
    if (selectedDifficulty !== '전체') {
      routes = routes.filter(r => r.difficulty === selectedDifficulty);
    }

    // AI 추천만
    if (showAIOnly) {
      routes = routes.filter(r => r.isAIRecommended);
    }

    // 정렬
    switch (sortBy) {
      case 'rating':
        routes.sort((a, b) => b.rating - a.rating);
        break;
      case 'most-used':
        routes.sort((a, b) => b.usedCount - a.usedCount);
        break;
      case 'newest':
        routes.sort((a, b) => b.id - a.id);
        break;
      case 'trending':
      default:
        routes.sort((a, b) => b.trendScore - a.trendScore);
        break;
    }

    return routes;
  }, [searchQuery, selectedSeason, selectedDifficulty, sortBy, showAIOnly]);

  const aiRecommendedRoutes = SAMPLE_ROUTES.filter(r => r.isAIRecommended)
    .sort((a, b) => b.trendScore - a.trendScore)
    .slice(0, 3);

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

        {/* AI Recommended (Featured) */}
        <section className="explore-section">
          <div className="section-header-row">
            <div className="section-title-group">
              <span className="ai-badge">AI</span>
              <h2 className="explore-section-title">맞춤 추천 경로</h2>
            </div>
            <p className="section-desc">사용자 데이터를 분석하여 추천하는 인기 경로</p>
          </div>

          <div className="featured-routes">
            {aiRecommendedRoutes.map((route, i) => (
              <div
                key={route.id}
                className={`featured-route-card ${route.colorTheme}-gradient`}
                onClick={() => navigate(`/trip/${route.id}`)}
              >
                <div className="featured-rank">#{i + 1}</div>
                <div className="featured-content">
                  <h3 className="featured-title">{route.title}</h3>
                  <p className="featured-desc">{route.description}</p>
                  <div className="featured-meta">
                    <span>{route.duration}</span>
                    <span>&middot;</span>
                    <span>{route.distance}</span>
                    <span>&middot;</span>
                    <span>{route.rating} ★</span>
                  </div>
                  <div className="featured-stops">
                    {route.stops.map((stop, j) => (
                      <React.Fragment key={j}>
                        <span className="stop-name">{stop.name}</span>
                        {j < route.stops.length - 1 && <span className="stop-arrow">→</span>}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
                <div className="featured-stats">
                  <span className="featured-stat">{route.usedCount.toLocaleString()}명 사용</span>
                </div>
              </div>
            ))}
          </div>
        </section>

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
              />
              {searchQuery && (
                <button className="explore-search-clear" onClick={() => setSearchQuery('')}>
                  &times;
                </button>
              )}
            </div>
          </div>

          <div className="explore-filters">
            <div className="filter-group">
              <span className="filter-label">시즌</span>
              <div className="filter-chips">
                {SEASONS.map(season => (
                  <button
                    key={season}
                    className={`filter-chip ${selectedSeason === season ? 'active' : ''}`}
                    onClick={() => setSelectedSeason(season)}
                  >
                    {season}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <span className="filter-label">난이도</span>
              <div className="filter-chips">
                {DIFFICULTIES.map(diff => (
                  <button
                    key={diff}
                    className={`filter-chip ${selectedDifficulty === diff ? 'active' : ''}`}
                    onClick={() => setSelectedDifficulty(diff)}
                  >
                    {diff}
                  </button>
                ))}
              </div>
            </div>

            <div className="filter-row">
              <button
                className={`ai-filter-btn ${showAIOnly ? 'active' : ''}`}
                onClick={() => setShowAIOnly(!showAIOnly)}
              >
                <span className="ai-badge-sm">AI</span>
                AI 추천만
              </button>

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
        </section>

        {/* Route List */}
        <section className="explore-section">
          <div className="section-header-row">
            <h2 className="explore-section-title">
              전체 경로 <span className="route-count">{filteredRoutes.length}</span>
            </h2>
          </div>

          {filteredRoutes.length === 0 ? (
            <div className="explore-empty">
              <p>검색 결과가 없습니다.</p>
              <button className="explore-reset-btn" onClick={() => {
                setSearchQuery('');
                setSelectedSeason('전체');
                setSelectedDifficulty('전체');
                setShowAIOnly(false);
              }}>
                필터 초기화
              </button>
            </div>
          ) : (
            <div className="route-grid">
              {filteredRoutes.map((route) => (
                <div
                  key={route.id}
                  className="route-card"
                  onClick={() => navigate(`/trip/${route.id}`)}
                >
                  {/* Card Header */}
                  <div className={`route-card-header ${route.colorTheme}-gradient`}>
                    <div className="route-card-overlay">
                      {route.isAIRecommended && <span className="route-ai-badge">AI 추천</span>}
                      <div className="route-card-stops">
                        {route.stops.slice(0, 3).map((stop, j) => (
                          <React.Fragment key={j}>
                            <span>{stop.name}</span>
                            {j < Math.min(route.stops.length, 3) - 1 && <span className="stop-arrow-sm">→</span>}
                          </React.Fragment>
                        ))}
                        {route.stops.length > 3 && <span className="stop-more">+{route.stops.length - 3}</span>}
                      </div>
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="route-card-body">
                    <h3 className="route-card-title">{route.title}</h3>
                    <p className="route-card-desc">{route.description}</p>

                    <div className="route-card-meta">
                      <span className="route-meta-item">{route.duration}</span>
                      <span className="route-meta-item">{route.distance}</span>
                      <span className="route-meta-item">{route.season}</span>
                      <span className={`route-difficulty ${route.difficulty}`}>{route.difficulty}</span>
                    </div>

                    <div className="route-card-footer">
                      <div className="route-rating">
                        <span className="rating-star">★</span>
                        <span className="rating-value">{route.rating}</span>
                        <span className="rating-count">({route.reviewCount})</span>
                      </div>
                      <div className="route-usage">
                        {route.usedCount.toLocaleString()}명 사용
                      </div>
                    </div>

                    <div className="route-card-tags">
                      {route.tags.slice(0, 3).map(tag => (
                        <span key={tag} className="route-tag">#{tag}</span>
                      ))}
                    </div>
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
