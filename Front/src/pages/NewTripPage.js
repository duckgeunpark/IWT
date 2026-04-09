import React, { useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { useDispatch } from 'react-redux';
import exifr from 'exifr';
import { addPhoto, setUploadProgress, setFilterResult } from '../store/photoSlice';
import { fileStore } from '../store/fileStore';
import { compressImage, createThumbnail } from '../utils/imageCompressor';
import { computeFileHash } from '../utils/fileHash';
import { apiClient } from '../services/apiClient';
import { useToast } from '../components/Toast';
import Header from '../components/Header';
import '../styles/NewTripPage.css';

// ── 사진 활용 상태 헬퍼 ──
const getUsageInfo = (usage, filterResult) => {
  if (filterResult?.is_duplicate) return { label: '중복 제거', cls: 'dup' };
  switch (usage) {
    case 'used':   return { label: 'GPS+게시글 활용', cls: 'used' };
    case '0001':   return { label: 'GPS 없음', cls: 'no-gps' };
    case '0002':   return { label: '시간대 불일치', cls: 'trash' };
    case '0003':   return { label: '연사 그룹', cls: 'burst' };
    case '0004':   return { label: 'GPS 이상치', cls: 'trash' };
    case '0005':   return { label: '날짜 없음', cls: 'no-gps' };
    default:       return { label: '분석 중', cls: 'neutral' };
  }
};

// ── 여행 스타일 옵션 ──
const TRAVEL_STYLES = [
  { id: 'healing', icon: '🧘', label: '힐링', desc: '느긋하게 쉬는 여행' },
  { id: 'food', icon: '🍜', label: '맛집', desc: '현지 음식 탐방' },
  { id: 'activity', icon: '🏄', label: '액티비티', desc: '스포츠·체험 중심' },
  { id: 'culture', icon: '🏛️', label: '문화·역사', desc: '박물관·유적지 탐방' },
  { id: 'nature', icon: '🏔️', label: '자연', desc: '산·바다·국립공원' },
  { id: 'city', icon: '🌃', label: '도시', desc: '쇼핑·카페·야경' },
  { id: 'photo', icon: '📸', label: '포토', desc: '사진 명소 위주' },
  { id: 'budget', icon: '💰', label: '가성비', desc: '저예산 알찬 여행' },
];

const DURATIONS = [
  { id: 'day', label: '당일치기' },
  { id: '1n2d', label: '1박 2일' },
  { id: '2n3d', label: '2박 3일' },
  { id: '3n4d', label: '3박 4일' },
  { id: '4n5d', label: '4박 5일+' },
];

const NewTripPage = ({ toggleTheme, theme }) => {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const toast = useToast();
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

  // ── 공통 상태 ──
  const [mode, setMode] = useState(null); // null, 'record', 'plan'
  const [step, setStep] = useState(0);

  // ── 기록 모드 상태 ──
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [processProgress, setProcessProgress] = useState({ current: 0, total: 0 });
  const fileInputRef = useRef(null);

  // ── 필터링 상태 ──
  const [filterSummary, setFilterSummary] = useState(null);
  const [photosWithStatus, setPhotosWithStatus] = useState([]); // 사진별 필터 결과
  const [isFiltering, setIsFiltering] = useState(false);
  const [generatedDraft, setGeneratedDraft] = useState(null);

  // ── 계획 모드 상태 ──
  const [destination, setDestination] = useState('');
  const [selectedStyles, setSelectedStyles] = useState([]);
  const [selectedDuration, setSelectedDuration] = useState(null);
  const [companions, setCompanions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  // ═══════════════════════════════════════════
  // 기록 모드 — 사진 업로드 & 처리 (hooks must be before early returns)
  // ═══════════════════════════════════════════

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
    if (files.length > 0) {
      addFiles(files);
    }
  }, []);

  // ── 인증 체크 (after all hooks) ──
  if (!isLoading && !isAuthenticated) {
    return (
      <div className="new-trip-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="new-trip-auth-prompt">
          <div className="prompt-icon-large">✈️</div>
          <h2>로그인이 필요합니다</h2>
          <p>여행 기록을 만들려면 로그인해주세요.</p>
          <button className="prompt-cta" onClick={() => loginWithRedirect()}>
            로그인하고 시작하기
          </button>
        </div>
      </div>
    );
  }

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      addFiles(files);
    }
    e.target.value = '';
  };

  const addFiles = (newFiles) => {
    const validFiles = newFiles.filter(f => {
      if (!f.type.startsWith('image/')) {
        toast.warning(`${f.name}은 이미지가 아닙니다.`);
        return false;
      }
      if (f.size > 10 * 1024 * 1024) {
        toast.warning(`${f.name} 크기 초과 (최대 10MB)`);
        return false;
      }
      return true;
    });

    const withPreviews = validFiles.map(file => ({
      file,
      id: Date.now() + Math.random(),
      preview: URL.createObjectURL(file),
      name: file.name,
    }));

    setUploadedFiles(prev => [...prev, ...withPreviews]);
  };

  const removeFile = (id) => {
    setUploadedFiles(prev => {
      const file = prev.find(f => f.id === id);
      if (file?.preview) URL.revokeObjectURL(file.preview);
      return prev.filter(f => f.id !== id);
    });
  };

  const processAndCreateTrip = async () => {
    if (uploadedFiles.length === 0) return;

    setIsProcessing(true);
    setProcessProgress({ current: 0, total: uploadedFiles.length });

    try {
      const filterInput = [];
      const processedFiles = []; // 사진별 상태 추적용

      for (let i = 0; i < uploadedFiles.length; i++) {
        const { file, preview, name, id: uploadedFileId } = uploadedFiles[i];
        setProcessProgress({ current: i + 1, total: uploadedFiles.length });

        // 파일 해시 계산 (중복 감지용)
        const fileHash = await computeFileHash(file);

        // EXIF 추출
        let exifData = { hasExif: false, backendData: null };
        let gps = null;
        let takenAtLocal = null;
        try {
          const raw = await exifr.parse(file, { tiff: true, gps: true });
          const lat = raw?.latitude || raw?.GPSLatitude;
          const lng = raw?.longitude || raw?.GPSLongitude;
          if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
            gps = { lat: parseFloat(lat), lng: parseFloat(lng) };
            if (raw?.GPSAltitude) gps.alt = parseFloat(raw.GPSAltitude);
          }

          const dateTime = raw?.DateTime || raw?.DateTimeOriginal || raw?.CreateDate;
          if (dateTime) {
            const d = new Date(dateTime);
            if (!isNaN(d.getTime())) takenAtLocal = d.toISOString();
          }

          exifData = {
            hasExif: !!raw,
            backendData: { gps, takenAtLocal, originalFilename: file.name, fileSizeBytes: file.size },
          };
        } catch (_) { /* EXIF 없어도 진행 */ }

        // 압축 & 썸네일
        const compressed = await compressImage(file);
        const thumbnail = await createThumbnail(file);

        const photoId = Date.now() + Math.random();
        fileStore.set(photoId, compressed);

        dispatch(addPhoto({
          photo: {
            id: photoId,
            name: file.name,
            size: compressed.size,
            type: compressed.type,
            preview: thumbnail,
          },
          gpsData: gps,
          exifData,
        }));

        // 필터링용 데이터 수집
        const photoIdStr = String(photoId);
        filterInput.push({
          id: photoIdStr,
          file_name: file.name,
          file_size: file.size,
          file_hash: fileHash,
          gps: gps,
          taken_at: takenAtLocal,
          content_type: file.type,
        });

        // 사진별 상태 추적
        processedFiles.push({ uploadedFileId, preview, name: file.name, photoId: photoIdStr });
      }

      dispatch(setUploadProgress({ current: 0, total: 0 }));

      // 사진 필터링 파이프라인 실행
      setIsFiltering(true);
      let filterSummaryResult = null;
      try {
        const filterResponse = await apiClient.post('/api/v1/photos/filter', {
          photos: filterInput,
          enable_ai_quality: false,
        });
        filterSummaryResult = filterResponse.summary;
        setFilterSummary(filterResponse.summary);
        dispatch(setFilterResult(filterResponse));

        // 사진별 필터 결과 매핑
        const filterPhotoMap = {};
        (filterResponse.photos || []).forEach(p => { filterPhotoMap[p.id] = p; });
        setPhotosWithStatus(processedFiles.map(pf => ({
          ...pf,
          filterResult: filterPhotoMap[pf.photoId] || null,
        })));

        const s = filterResponse.summary;
        const msgs = [];
        if (s.duplicates_removed > 0) msgs.push(`중복 ${s.duplicates_removed}장 제거`);
        if (s.burst_groups > 0) msgs.push(`연사 ${s.burst_groups}그룹 감지`);
        if (s.trash_removed > 0) msgs.push(`불필요 ${s.trash_removed}장 구분`);
        if (s.no_gps_count > 0) msgs.push(`GPS 없음 ${s.no_gps_count}장`);

        toast.success(
          `${uploadedFiles.length}장 분석 완료! 활용 가능: ${s.usable_photos}장` +
          (msgs.length > 0 ? ` (${msgs.join(', ')})` : '')
        );
      } catch (filterErr) {
        console.warn('필터링 API 실패 (무시하고 계속):', filterErr);
        toast.success(`${uploadedFiles.length}장 처리 완료!`);
      } finally {
        setIsFiltering(false);
      }

      // AI 초안 생성 + 하이라이트 사진 선정 (병렬 실행)
      let draft = null;
      try {
        const photoData = filterInput.map(p => ({
          name: p.file_name,
          captureTime: p.taken_at,
          gps: p.gps,
        }));
        const locationData = filterInput
          .filter(p => p.gps)
          .map((p) => ({ name: p.file_name, coordinates: p.gps, time: p.taken_at }));

        const highlightInput = filterInput.map(p => ({
          id: p.id,
          file_name: p.file_name,
          gps: p.gps,
          taken_at: p.taken_at,
          file_size: p.file_size,
        }));

        const [llmRes, highlightRes] = await Promise.allSettled([
          apiClient.post('/api/v1/llm/generate-itinerary', {
            route_data: {
              photos: photoData,
              locations: locationData,
              total_photos: filterInput.length,
            },
            user_preferences: { language: 'ko', format: 'markdown' },
          }),
          filterInput.length >= 3
            ? apiClient.post('/api/v1/llm/highlight-photos', {
                photos: highlightInput,
                max_highlights: Math.min(5, Math.ceil(filterInput.length * 0.3)),
              })
            : Promise.resolve(null),
        ]);

        const llmData = llmRes.status === 'fulfilled' ? llmRes.value : null;
        const highlightData = highlightRes.status === 'fulfilled' ? highlightRes.value : null;

        if (llmData?.success && llmData?.itinerary) {
          draft = {
            content: llmData.itinerary,
            title: llmData.title || null,
            tags: llmData.tags || null,
            highlightedIds: highlightData?.highlighted_ids || null,
          };
          toast.success('AI 초안 생성 완료! 내용을 검토하고 수정하세요.');
        } else if (highlightData?.highlighted_ids) {
          draft = { highlightedIds: highlightData.highlighted_ids };
        }
      } catch (llmErr) {
        console.warn('AI 초안 생성 실패 (무시하고 계속):', llmErr);
      }

      // 분석 결과 요약 toast만 보여주고 바로 edit 이동
      if (filterSummaryResult) {
        const s = filterSummaryResult;
        const parts = [`활용 가능 ${s.usable_photos}장`];
        if (s.duplicates_removed > 0) parts.push(`중복 ${s.duplicates_removed}장 제외`);
        if (s.no_gps_count > 0) parts.push(`GPS 없음 ${s.no_gps_count}장`);
        toast.success(`분석 완료 — ${parts.join(', ')}`);
      }
      goToEditPage(draft);
    } catch (err) {
      toast.error('처리 중 오류가 발생했습니다.');
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  const goToEditPage = (draft) => {
    uploadedFiles.forEach(f => { if (f.preview) URL.revokeObjectURL(f.preview); });
    navigate('/trip/new/edit', { state: { fromRecord: true, draft: draft || generatedDraft } });
  };

  // ═══════════════════════════════════════════
  // 계획 모드 — 목적지 + 스타일 입력
  // ═══════════════════════════════════════════

  const toggleStyle = (styleId) => {
    setSelectedStyles(prev =>
      prev.includes(styleId)
        ? prev.filter(s => s !== styleId)
        : prev.length < 3 ? [...prev, styleId] : prev
    );
  };

  const generatePlan = async () => {
    if (!destination.trim()) {
      toast.warning('목적지를 입력해주세요.');
      return;
    }

    setIsGenerating(true);
    try {
      // TODO: 백엔드 API 호출
      // POST /api/v1/trips/plan
      // { destination, styles: selectedStyles, duration: selectedDuration, companions }

      // 지금은 시뮬레이션 (2초 딜레이)
      await new Promise(resolve => setTimeout(resolve, 2000));

      toast.success('AI가 여행 경로를 생성했습니다!');
      navigate('/trip/new/edit', {
        state: {
          fromPlan: true,
          planData: { destination, styles: selectedStyles, duration: selectedDuration, companions }
        }
      });
    } catch (err) {
      toast.error('경로 생성에 실패했습니다.');
    } finally {
      setIsGenerating(false);
    }
  };

  // ═══════════════════════════════════════════
  // 렌더링
  // ═══════════════════════════════════════════

  // ── 모드 선택 화면 ──
  if (mode === null) {
    return (
      <div className="new-trip-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="new-trip-content">
          <div className="mode-select-section">
            <h1 className="mode-select-title">어떤 여행을 시작할까요?</h1>
            <p className="mode-select-subtitle">사진을 올려 기록하거나, AI에게 경로를 추천받으세요</p>

            <div className="mode-cards">
              {/* 기록 모드 */}
              <button className="mode-card" onClick={() => { setMode('record'); setStep(1); }}>
                <div className="mode-card-icon record-icon">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <path d="m21 15-5-5L5 21" />
                  </svg>
                </div>
                <h2 className="mode-card-title">여행 기록하기</h2>
                <p className="mode-card-desc">
                  사진만 올리면 끝!<br />
                  AI가 경로와 기록을 자동 생성합니다
                </p>
                <span className="mode-card-hint">GPS 정보가 있는 사진 권장</span>
              </button>

              {/* 계획 모드 */}
              <button className="mode-card" onClick={() => { setMode('plan'); setStep(1); }}>
                <div className="mode-card-icon plan-icon">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
                  </svg>
                </div>
                <h2 className="mode-card-title">여행 계획하기</h2>
                <p className="mode-card-desc">
                  가고 싶은 곳만 알려주세요<br />
                  AI + 커뮤니티 데이터로 경로 추천
                </p>
                <span className="mode-card-hint">여행 스타일 선택 가능</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── 기록 모드: 사진 업로드 ──
  if (mode === 'record') {
    return (
      <div className="new-trip-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="new-trip-content">
          <div className="wizard-container">
            {/* 상단 바 */}
            <div className="wizard-header">
              <button className="wizard-back" onClick={() => { setMode(null); setStep(0); setUploadedFiles([]); }}>
                ← 뒤로
              </button>
              <div className="wizard-step-indicator">
                <span className="step-label">사진 업로드</span>
              </div>
              <div className="wizard-header-spacer" />
            </div>

            {/* 드래그 & 드롭 영역 */}
            <div
              className={`upload-zone ${isDragging ? 'dragging' : ''} ${uploadedFiles.length > 0 ? 'has-files' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileSelect}
              />

              {uploadedFiles.length === 0 ? (
                <div className="upload-zone-empty">
                  <div className="upload-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <p className="upload-main-text">여행 사진을 드래그하거나 클릭하세요</p>
                  <p className="upload-sub-text">GPS 정보가 있으면 자동으로 경로가 생성됩니다</p>
                </div>
              ) : (
                <div className="upload-zone-filled" onClick={(e) => e.stopPropagation()}>
                  <div className="photo-grid-preview">
                    {uploadedFiles.map((f) => (
                      <div key={f.id} className="photo-preview-item">
                        <img src={f.preview} alt={f.name} />
                        <button
                          className="photo-remove-btn"
                          onClick={(e) => { e.stopPropagation(); removeFile(f.id); }}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                    <button
                      className="photo-add-more"
                      onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                    >
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="12" y1="5" x2="12" y2="19" />
                        <line x1="5" y1="12" x2="19" y2="12" />
                      </svg>
                      <span>추가</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* 파일 카운트 & 처리 버튼 */}
            {uploadedFiles.length > 0 && step === 1 && (
              <div className="upload-actions">
                <span className="upload-count">{uploadedFiles.length}장 선택됨</span>

                {isProcessing || isFiltering ? (
                  <div className="processing-status">
                    <div className="processing-bar">
                      <div
                        className="processing-fill"
                        style={{ width: isFiltering ? '100%' : `${(processProgress.current / processProgress.total) * 100}%` }}
                      />
                    </div>
                    <span className="processing-text">
                      {isFiltering
                        ? 'AI 사진 필터링 중...'
                        : `${processProgress.current}/${processProgress.total} 처리 중...`
                      }
                    </span>
                  </div>
                ) : (
                  <button className="record-start-btn" onClick={processAndCreateTrip}>
                    AI로 여행 기록 생성하기 →
                  </button>
                )}
              </div>
            )}

          </div>
        </div>
      </div>
    );
  }

  // ── 계획 모드: 목적지 + 스타일 ──
  if (mode === 'plan') {
    return (
      <div className="new-trip-page">
        <Header toggleTheme={toggleTheme} theme={theme} />
        <div className="new-trip-content">
          <div className="wizard-container">
            {/* 상단 바 */}
            <div className="wizard-header">
              <button className="wizard-back" onClick={() => {
                if (step > 1) { setStep(step - 1); }
                else { setMode(null); setStep(0); }
              }}>
                ← 뒤로
              </button>
              <div className="wizard-step-indicator">
                <div className="step-dots">
                  {[1, 2, 3].map(s => (
                    <div key={s} className={`step-dot ${step >= s ? 'active' : ''} ${step === s ? 'current' : ''}`} />
                  ))}
                </div>
              </div>
              <div className="wizard-header-spacer" />
            </div>

            {/* Step 1: 목적지 */}
            {step === 1 && (
              <div className="plan-step">
                <h2 className="plan-step-title">어디로 가고 싶나요?</h2>
                <p className="plan-step-subtitle">도시, 나라, 또는 지역을 입력하세요</p>

                <div className="plan-input-group">
                  <input
                    type="text"
                    className="plan-destination-input"
                    placeholder="예: 제주도, 도쿄, 파리..."
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                    autoFocus
                    onKeyDown={(e) => { if (e.key === 'Enter' && destination.trim()) setStep(2); }}
                  />
                </div>

                <div className="plan-popular">
                  <span className="plan-popular-label">인기 목적지</span>
                  <div className="plan-popular-tags">
                    {['제주도', '부산', '도쿄', '오사카', '방콕', '파리', '다낭', '발리'].map(place => (
                      <button
                        key={place}
                        className={`popular-tag ${destination === place ? 'active' : ''}`}
                        onClick={() => setDestination(place)}
                      >
                        {place}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  className="plan-next-btn"
                  disabled={!destination.trim()}
                  onClick={() => setStep(2)}
                >
                  다음 →
                </button>
              </div>
            )}

            {/* Step 2: 여행 스타일 */}
            {step === 2 && (
              <div className="plan-step">
                <h2 className="plan-step-title">어떤 여행을 원하세요?</h2>
                <p className="plan-step-subtitle">최대 3개까지 선택 가능 (선택사항)</p>

                <div className="style-grid">
                  {TRAVEL_STYLES.map(style => (
                    <button
                      key={style.id}
                      className={`style-card ${selectedStyles.includes(style.id) ? 'selected' : ''}`}
                      onClick={() => toggleStyle(style.id)}
                    >
                      <span className="style-icon">{style.icon}</span>
                      <span className="style-label">{style.label}</span>
                      <span className="style-desc">{style.desc}</span>
                      {selectedStyles.includes(style.id) && <span className="style-check">✓</span>}
                    </button>
                  ))}
                </div>

                <button className="plan-next-btn" onClick={() => setStep(3)}>
                  {selectedStyles.length > 0 ? '다음 →' : '건너뛰기 →'}
                </button>
              </div>
            )}

            {/* Step 3: 기간 + 동행 + 생성 */}
            {step === 3 && (
              <div className="plan-step">
                <h2 className="plan-step-title">마지막으로 몇 가지만!</h2>
                <p className="plan-step-subtitle">선택사항 — 바로 생성해도 됩니다</p>

                <div className="plan-final-options">
                  <div className="option-group">
                    <label className="option-label">여행 기간</label>
                    <div className="duration-chips">
                      {DURATIONS.map(d => (
                        <button
                          key={d.id}
                          className={`duration-chip ${selectedDuration === d.id ? 'active' : ''}`}
                          onClick={() => setSelectedDuration(selectedDuration === d.id ? null : d.id)}
                        >
                          {d.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="option-group">
                    <label className="option-label">동행 (선택)</label>
                    <input
                      type="text"
                      className="option-input"
                      placeholder="예: 친구 2명, 가족, 혼자..."
                      value={companions}
                      onChange={(e) => setCompanions(e.target.value)}
                    />
                  </div>
                </div>

                {/* 요약 */}
                <div className="plan-summary">
                  <div className="summary-item">
                    <span className="summary-label">목적지</span>
                    <span className="summary-value">{destination}</span>
                  </div>
                  {selectedStyles.length > 0 && (
                    <div className="summary-item">
                      <span className="summary-label">스타일</span>
                      <span className="summary-value">
                        {selectedStyles.map(id => TRAVEL_STYLES.find(s => s.id === id)?.label).join(', ')}
                      </span>
                    </div>
                  )}
                  {selectedDuration && (
                    <div className="summary-item">
                      <span className="summary-label">기간</span>
                      <span className="summary-value">{DURATIONS.find(d => d.id === selectedDuration)?.label}</span>
                    </div>
                  )}
                </div>

                <button
                  className="plan-generate-btn"
                  onClick={generatePlan}
                  disabled={isGenerating}
                >
                  {isGenerating ? (
                    <>
                      <span className="gen-spinner" />
                      AI가 경로를 만드는 중...
                    </>
                  ) : (
                    <>AI로 여행 경로 생성하기</>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default NewTripPage;
