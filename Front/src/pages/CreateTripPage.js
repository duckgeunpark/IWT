import React, { useState, useEffect, useCallback } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useSelector, useDispatch } from 'react-redux';
import { clearPhotos, loadExistingPhoto, applyHighlights } from '../store/photoSlice';
import { clearClusters } from '../store/clusterSlice';
import { useNavigate, useLocation, useParams } from 'react-router-dom';
import ImagePanel from '../components/ImagePanel';
import DocumentPanel from '../components/DocumentPanel';
import MapPanel from '../components/MapPanel';
import Resizer from '../components/Resizer';
import { useToast } from '../components/Toast';
import { apiClient } from '../services/apiClient';
import { fileStore } from '../store/fileStore';
import '../styles/CreateTripPage.css';

const buildDefaultTitle = (userName, photos) => {
  if (!photos || photos.length === 0) return userName ? `${userName}의 여행 기록` : '새 여행 기록';
  const dates = photos
    .map(p => p.captureTimestamp)
    .filter(Boolean)
    .sort((a, b) => a - b);
  let datePart = '';
  if (dates.length > 0) {
    const d = new Date(dates[0]);
    datePart = ` (${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')})`;
  }
  return userName ? `${userName}의 여행 기록${datePart}` : `여행 기록${datePart}`;
};

const CreateTripPage = ({ toggleTheme, theme }) => {
  const { user, isAuthenticated, isLoading } = useAuth0();
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const toast = useToast();
  const routeLocation = useLocation();
  const { id: editPostId } = useParams();  // defined when /trip/:id/edit

  // 편집 모드 vs 신규 작성 모드
  const isEditMode = Boolean(editPostId);

  const draft = routeLocation.state?.draft;
  const photos = useSelector(state => state.photos.photos);
  const locations = useSelector(state => state.photos.locations);
  const clusters = useSelector(state => state.clusters?.clusters || []);

  const [tripTitle, setTripTitle] = useState(
    draft?.title || buildDefaultTitle(user?.name, photos)
  );
  const [content, setContent] = useState(draft?.content || null);
  const [tags, setTags] = useState(draft?.tags || []);
  const [tagInput, setTagInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isGeneratingContent, setIsGeneratingContent] = useState(false);
  const [editLoading, setEditLoading] = useState(isEditMode);
  const [isDraftPost, setIsDraftPost] = useState(false);
  const [showLLMSettings, setShowLLMSettings] = useState(false);
  const [llmPrefs, setLlmPrefs] = useState({ tone: 'casual', style: 'blog', lang: 'ko', stage1_extra: '', stage2_extra: '', stage3_extra: '' });
  const [llmPrefsSaving, setLlmPrefsSaving] = useState(false);

  // ── 신규 모드: 이전 사진 세션 초기화 + 하이라이트 적용 ──
  // fromRecord: NewTripPage에서 사진을 이미 Redux에 넣고 넘어온 경우 → 초기화 금지
  useEffect(() => {
    if (isEditMode) return;
    if (routeLocation.state?.fromRecord) {
      // 하이라이트 사진 적용
      if (draft?.highlightedIds?.length) {
        dispatch(applyHighlights(draft.highlightedIds));
      }
      return;
    }
    dispatch(clearPhotos());
    fileStore.clear();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 편집 모드: 기존 게시글 데이터 + 사진 로드 ──
  useEffect(() => {
    if (!isEditMode) return;
    let cancelled = false;

    dispatch(clearPhotos());
    fileStore.clear();

    const load = async () => {
      try {
        const [post, photosData] = await Promise.all([
          apiClient.get(`/api/v1/posts/${editPostId}`),
          apiClient.get(`/api/v1/posts/${editPostId}/photos`),
        ]);
        if (cancelled) return; // 이전 실행 결과 무시
        setTripTitle(post.title || '');
        setContent(post.description || '');
        setTags(post.tags || []);
        setIsDraftPost(post.status === 'draft');
        for (const photo of photosData.photos || []) {
          dispatch(loadExistingPhoto(photo));
        }
      } catch (err) {
        if (cancelled) return;
        console.error('게시글 로드 실패:', err);
        toast.error('게시글을 불러오지 못했습니다.');
      } finally {
        if (!cancelled) setEditLoading(false);
      }
    };
    load();

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditMode, editPostId]);

  // ── AI 자동 생성 (신규 모드) — S3 temp 업로드 → auto-create → 편집 모드로 이동 ──
  useEffect(() => {
    if (isEditMode || draft?.content || photos.length === 0 || isGeneratingContent) return;
    const generateContent = async () => {
      setIsGeneratingContent(true);
      try {
        // 1. S3 temp 업로드
        const photoPayload = [];
        for (const photo of photos) {
          const file = fileStore.get(photo.id);
          if (!file) continue;
          const presignedData = await apiClient.post('/api/v1/photos/presigned-url', {
            file_name: photo.name, content_type: photo.type,
          });
          const uploadRes = await fetch(presignedData.presigned_url, {
            method: 'PUT', body: file, headers: { 'Content-Type': photo.type },
          });
          if (!uploadRes.ok) continue;
          photoPayload.push({
            file_key: presignedData.file_key,
            file_name: photo.name,
            file_size: photo.size,
            content_type: photo.type || 'image/jpeg',
            _lat: photo.gpsData?.lat || null,
            _lon: photo.gpsData?.lng || null,
            location_info: null,
            exif_data: { datetime: photo.captureTime || null },
          });
        }

        if (photoPayload.length === 0) {
          toast.warning('업로드 가능한 사진이 없습니다.');
          return;
        }

        // 2. 3단계 LLM 파이프라인 + 게시글 자동 생성
        const res = await apiClient.post('/api/v1/posts/auto-create', photoPayload);

        // 3. 완료 → 편집 모드로 이동 (생성된 post의 edit 페이지)
        dispatch(clearPhotos());
        dispatch(clearClusters());
        fileStore.clear();
        navigate(`/trip/${res.id}/edit`);
      } catch (err) {
        console.warn('AI 초안 자동 생성 실패:', err);
        toast.error('AI 게시글 생성에 실패했습니다. 다시 시도해주세요.');
      } finally {
        setIsGeneratingContent(false);
      }
    };
    generateContent();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── ai-update 완료 후 title/tags 동기화 ──
  const handleAIResult = useCallback(({ title, tags: newTags }) => {
    if (title) setTripTitle(title);
    if (newTags?.length) setTags(newTags);
  }, []);

  // ── LLM 설정 로드 (편집 모드 또는 모달 오픈 시) ──
  useEffect(() => {
    if (!isEditMode) return;
    apiClient.get('/api/v1/llm-preferences/').then(prefs => {
      setLlmPrefs({
        tone: prefs.tone || 'casual',
        style: prefs.style || 'blog',
        lang: prefs.lang || 'ko',
        stage1_extra: prefs.stage1_extra || '',
        stage2_extra: prefs.stage2_extra || '',
        stage3_extra: prefs.stage3_extra || '',
      });
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditMode]);

  const handleLLMSettingsOpen = useCallback(async () => {
    try {
      const prefs = await apiClient.get('/api/v1/llm-preferences/');
      setLlmPrefs({
        tone: prefs.tone || 'casual',
        style: prefs.style || 'blog',
        lang: prefs.lang || 'ko',
        stage1_extra: prefs.stage1_extra || '',
        stage2_extra: prefs.stage2_extra || '',
        stage3_extra: prefs.stage3_extra || '',
      });
    } catch (e) {}
    setShowLLMSettings(true);
  }, []);

  const handleLLMSettingsSave = useCallback(async () => {
    setLlmPrefsSaving(true);
    try {
      await apiClient.put('/api/v1/llm-preferences/', {
        tone: llmPrefs.tone,
        style: llmPrefs.style,
        lang: llmPrefs.lang,
        stage1_extra: llmPrefs.stage1_extra || null,
        stage2_extra: llmPrefs.stage2_extra || null,
        stage3_extra: llmPrefs.stage3_extra || null,
      });
      toast.success('AI 설정이 저장됐습니다.');
      setShowLLMSettings(false);
    } catch (e) {
      toast.error('설정 저장에 실패했습니다.');
    } finally {
      setLlmPrefsSaving(false);
    }
  }, [llmPrefs, toast]);

  // ── 인증 확인 ──
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      alert('게시글을 작성하려면 로그인이 필요합니다.');
      navigate('/');
    }
  }, [isLoading, isAuthenticated, navigate]);

  // ── 패널 너비 ──
  const [leftWidth, setLeftWidth] = useState(25);
  const [centerWidth, setCenterWidth] = useState(50);
  const [rightWidth, setRightWidth] = useState(25);
  const [dragStartState, setDragStartState] = useState({ left: 25, center: 50, right: 25 });
  const [activeTab, setActiveTab] = useState('image');
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 992);
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // ── 임시저장 (신규 모드: S3 업로드 + draft POST → edit 모드로 이동) ──
  const handleTempSave = async () => {
    if (isEditMode) {
      // edit 모드 (draft): 현재 draft 상태 유지하며 업데이트
      setIsUploading(true);
      try {
        const keepPhotoIds = photos.filter(p => p.isExisting).map(p => p.dbId);
        const newPhotos = [];
        let updatedContent = content || '';
        for (const photo of photos.filter(p => !p.isExisting)) {
          const file = fileStore.get(photo.id);
          if (!file) continue;
          const presignedData = await apiClient.post('/api/v1/photos/presigned-url', {
            file_name: photo.name, content_type: photo.type,
          });
          await fetch(presignedData.presigned_url, { method: 'PUT', body: file, headers: { 'Content-Type': photo.type } });
          const permanentKey = `photos/${user.sub}/${Date.now()}_${photo.name}`;
          await apiClient.post('/api/v1/photos/move-to-permanent', { temp_key: presignedData.file_key, permanent_key: permanentKey });
          newPhotos.push({ file_key: permanentKey, file_name: photo.name, file_size: photo.size, content_type: photo.type || 'image/jpeg' });
          if (photo.preview && updatedContent.includes(photo.preview)) {
            updatedContent = updatedContent.replaceAll(photo.preview, `/api/v1/photos/download/${permanentKey}`);
          }
        }
        await apiClient.put(`/api/v1/posts/${editPostId}`, {
          title: tripTitle, description: updatedContent, tags, status: 'draft',
          keep_photo_ids: keepPhotoIds, new_photos: newPhotos,
        });
        toast.success('임시저장 완료!');
      } catch (err) {
        toast.error(err.message || '임시저장에 실패했습니다.');
      } finally {
        setIsUploading(false);
      }
      return;
    }

    // 신규 모드: 사진 업로드 + draft 생성 → /trip/:id/edit 이동
    if (photos.length === 0) {
      toast.warning('사진을 먼저 업로드해주세요.');
      return;
    }
    setIsUploading(true);
    try {
      const uploadedPhotos = [];
      let updatedContent = content || '';
      for (const photo of photos) {
        const file = fileStore.get(photo.id);
        if (!file) continue;
        const presignedData = await apiClient.post('/api/v1/photos/presigned-url', {
          file_name: photo.name, content_type: photo.type,
        });
        const uploadRes = await fetch(presignedData.presigned_url, { method: 'PUT', body: file, headers: { 'Content-Type': photo.type } });
        if (!uploadRes.ok) throw new Error(`업로드 실패: ${photo.name}`);
        const permanentKey = `photos/${user.sub}/${Date.now()}_${photo.name}`;
        await apiClient.post('/api/v1/photos/move-to-permanent', { temp_key: presignedData.file_key, permanent_key: permanentKey });
        uploadedPhotos.push({
          file_key: permanentKey, file_name: photo.name, file_size: photo.size,
          content_type: photo.type || 'image/jpeg',
          location_info: photo.gpsData ? { coordinates: { latitude: photo.gpsData.lat, longitude: photo.gpsData.lng } } : null,
        });
        if (photo.preview && updatedContent.includes(photo.preview)) {
          updatedContent = updatedContent.replaceAll(photo.preview, `/api/v1/photos/download/${permanentKey}`);
        }
      }
      const res = await apiClient.post('/api/v1/posts/', {
        title: tripTitle, description: updatedContent, tags, status: 'draft', photos: uploadedPhotos,
      });
      dispatch(clearPhotos());
      dispatch(clearClusters());
      fileStore.clear();
      toast.success('임시저장 완료!');
      navigate(`/trip/${res.id}/edit`);
    } catch (err) {
      toast.error(err.message || '임시저장에 실패했습니다.');
    } finally {
      setIsUploading(false);
    }
  };

  // ── 저장 (신규: POST, 편집: PUT) ──
  const handleSave = async () => {
    if (isEditMode) {
      setIsUploading(true);
      try {
        // 기존 사진 중 유지할 것들의 DB ID
        const keepPhotoIds = photos.filter(p => p.isExisting).map(p => p.dbId);

        // 새로 추가된 사진 업로드
        const newPhotos = [];
        let updatedContent = content || '';
        for (const photo of photos.filter(p => !p.isExisting)) {
          const file = fileStore.get(photo.id);
          if (!file) continue;
          const presignedData = await apiClient.post('/api/v1/photos/presigned-url', {
            file_name: photo.name,
            content_type: photo.type,
          });
          const uploadRes = await fetch(presignedData.presigned_url, {
            method: 'PUT',
            body: file,
            headers: { 'Content-Type': photo.type },
          });
          if (!uploadRes.ok) throw new Error(`업로드 실패: ${photo.name}`);
          const permanentKey = `photos/${user.sub}/${Date.now()}_${photo.name}`;
          await apiClient.post('/api/v1/photos/move-to-permanent', {
            temp_key: presignedData.file_key,
            permanent_key: permanentKey,
          });
          newPhotos.push({
            file_key: permanentKey,
            file_name: photo.name,
            file_size: photo.size,
            content_type: photo.type || 'image/jpeg',
          });
          if (photo.preview && updatedContent.includes(photo.preview)) {
            updatedContent = updatedContent.replaceAll(photo.preview, `/api/v1/photos/download/${permanentKey}`);
          }
        }

        await apiClient.put(`/api/v1/posts/${editPostId}`, {
          title: tripTitle,
          description: updatedContent,
          tags: tags,
          ...(isDraftPost && { status: 'published' }),
          keep_photo_ids: keepPhotoIds,
          new_photos: newPhotos,
        });
        dispatch(clearPhotos());
        dispatch(clearClusters());
        fileStore.clear();
        toast.success(isDraftPost ? '게시글이 게시됐습니다!' : '게시글이 수정됐습니다!');
        navigate(`/trip/${editPostId}`);
      } catch (err) {
        console.error(err);
        toast.error(err.message || '수정 중 오류가 발생했습니다.');
      } finally {
        setIsUploading(false);
      }
      return;
    }

    // 신규 모드: 사진 업로드 + 게시글 생성
    if (photos.length === 0) {
      toast.warning('업로드할 사진이 없습니다.');
      return;
    }
    setIsUploading(true);
    try {
      const uploadedPhotos = [];
      let updatedContent = content || '';
      for (const photo of photos) {
        const file = fileStore.get(photo.id);
        let fileKey;
        if (file) {
          const presignedData = await apiClient.post('/api/v1/photos/presigned-url', {
            file_name: photo.name,
            content_type: photo.type,
          });
          const uploadRes = await fetch(presignedData.presigned_url, {
            method: 'PUT',
            body: file,
            headers: { 'Content-Type': photo.type },
          });
          if (!uploadRes.ok) throw new Error(`업로드 실패: ${photo.name}`);
          const permanentKey = `photos/${user.sub}/${Date.now()}_${photo.name}`;
          await apiClient.post('/api/v1/photos/move-to-permanent', {
            temp_key: presignedData.file_key,
            permanent_key: permanentKey,
          });
          fileKey = permanentKey;
        }
        if (fileKey) {
          uploadedPhotos.push({
            file_key: fileKey,
            file_name: photo.name,
            file_size: photo.size,
            content_type: photo.type || 'image/jpeg',
            location_info: photo.gpsData ? {
              coordinates: { latitude: photo.gpsData.lat, longitude: photo.gpsData.lng },
            } : null,
          });
          if (photo.preview && updatedContent.includes(photo.preview)) {
            updatedContent = updatedContent.replaceAll(photo.preview, `/api/v1/photos/download/${fileKey}`);
          }
        }
      }
      await apiClient.post('/api/v1/posts/', {
        title: tripTitle,
        description: updatedContent,
        tags: tags,
        photos: uploadedPhotos,
      });
      dispatch(clearPhotos());
      dispatch(clearClusters());
      fileStore.clear();
      toast.success('게시글이 업로드됐습니다!');
      navigate('/');
    } catch (err) {
      console.error(err);
      toast.error(err.message || '업로드 중 오류가 발생했습니다.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleLeftResize = (totalDeltaX) => {
    const containerWidth = document.querySelector('.panels-container')?.clientWidth || 1200;
    const deltaPercent = (totalDeltaX / containerWidth) * 100;
    const availableSpace = 100 - rightWidth;
    const newLeftWidth = Math.max(15, Math.min(Math.min(70, availableSpace - 15), dragStartState.left + deltaPercent));
    const newCenterWidth = availableSpace - newLeftWidth;
    if (newCenterWidth >= 15) { setLeftWidth(newLeftWidth); setCenterWidth(newCenterWidth); }
  };

  const handleRightResize = (totalDeltaX) => {
    const containerWidth = document.querySelector('.panels-container')?.clientWidth || 1200;
    const deltaPercent = (totalDeltaX / containerWidth) * 100;
    const availableSpace = 100 - leftWidth;
    const newCenterWidth = Math.max(15, Math.min(Math.min(70, availableSpace - 15), dragStartState.center + deltaPercent));
    const newRightWidth = availableSpace - newCenterWidth;
    if (newRightWidth >= 15) { setCenterWidth(newCenterWidth); setRightWidth(newRightWidth); }
  };

  const handleDragStart = useCallback(() => {
    setDragStartState({ left: leftWidth, center: centerWidth, right: rightWidth });
  }, [leftWidth, centerWidth, rightWidth]);

  const handleDragEnd = useCallback(() => {
    setDragStartState({ left: leftWidth, center: centerWidth, right: rightWidth });
  }, [leftWidth, centerWidth, rightWidth]);

  if (isLoading || (isEditMode && editLoading)) {
    return (
      <div className="create-trip-page">
        <div className="page-header">
          <div className="header-left">
            <div className="logo-container" onClick={() => navigate('/')}>
              <div className="logo-avatar"></div>
              <div className="logo-text"><h1>IWT</h1><p>I Want. I Went. Trip.</p></div>
            </div>
          </div>
          <div className="title-section"><h1 className="page-title">로딩 중...</h1></div>
        </div>
        <div className="page-content">
          <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:'400px', fontSize:'18px' }}>
            {isEditMode ? '게시글을 불러오는 중...' : '인증 정보를 확인하고 있습니다...'}
          </div>
        </div>
      </div>
    );
  }

  if (isGeneratingContent) {
    return (
      <div className="create-trip-page">
        <div className="page-header">
          <div className="header-left">
            <div className="logo-container" onClick={() => navigate('/')}>
              <div className="logo-avatar"></div>
              <div className="logo-text"><h1>IWT</h1><p>I Want. I Went. Trip.</p></div>
            </div>
          </div>
          <div className="title-section"><h1 className="page-title">{tripTitle}</h1></div>
        </div>
        <div style={{ display:'flex', flexDirection:'column', justifyContent:'center', alignItems:'center', height:'calc(100vh - 80px)', gap:'24px' }}>
          <div style={{ width:'56px', height:'56px', border:'5px solid var(--border-color, #e0e0e0)', borderTopColor:'var(--primary-color, #4285F4)', borderRadius:'50%', animation:'spin 1s linear infinite' }} />
          <div style={{ textAlign:'center' }}>
            <p style={{ fontSize:'18px', fontWeight:'600', marginBottom:'8px' }}>AI가 여행 기록을 작성하는 중입니다</p>
            <p style={{ fontSize:'14px', color:'var(--text-secondary, #888)' }}>
              사진을 분석하고 여행 일지를 생성하고 있어요. 잠시만 기다려주세요.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="create-trip-page">
      {/* 헤더 */}
      <div className="page-header">
        <div className="header-left">
          <div className="logo-container" onClick={() => navigate('/')}>
            <div className="logo-avatar"></div>
            <div className="logo-text"><h1>IWT</h1><p>I Want. I Went. Trip.</p></div>
          </div>
        </div>

        <div className="title-section">
          {isEditing ? (
            <input
              type="text"
              className="title-input"
              value={tripTitle}
              onChange={(e) => setTripTitle(e.target.value)}
              onBlur={() => setIsEditing(false)}
              onKeyPress={(e) => e.key === 'Enter' && setIsEditing(false)}
              autoFocus
            />
          ) : (
            <h1 className="page-title" onClick={() => setIsEditing(true)}>{tripTitle}</h1>
          )}
        </div>

        <div className="header-actions">
          {toggleTheme && (
            <button className="theme-toggle" onClick={toggleTheme} title={theme === 'light' ? '다크 모드' : '라이트 모드'}>
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
          )}
          <button className="theme-toggle" onClick={handleLLMSettingsOpen} title="AI 생성 설정">⚙️</button>
          {(!isEditMode || isDraftPost) && (
            <button className="action-btn temp-save-btn" onClick={handleTempSave} disabled={isUploading}>
              임시저장
            </button>
          )}
          <button
            className="action-btn upload-btn"
            onClick={handleSave}
            disabled={isUploading}
          >
            {isUploading
              ? (isDraftPost ? '게시 중...' : isEditMode ? '저장 중...' : '업로드 중...')
              : (isDraftPost ? '게시하기' : isEditMode ? '저장' : '업로드')}
          </button>
          <div className="user-profile-icon">
            {isAuthenticated && user?.picture ? (
              <img src={user.picture} alt="프로필" className="profile-img" />
            ) : (
              <div className="default-profile">👤</div>
            )}
          </div>
        </div>
      </div>

      {/* 태그 바 */}
      <div className="tag-bar">
        <div className="tag-chips">
          {tags.map((tag, i) => (
            <span key={i} className="tag-chip">
              #{tag}
              <button
                className="tag-chip-remove"
                onClick={() => setTags(prev => prev.filter((_, idx) => idx !== i))}
              >×</button>
            </span>
          ))}
          <input
            className="tag-input"
            placeholder="태그 추가..."
            value={tagInput}
            onChange={e => setTagInput(e.target.value)}
            onKeyDown={e => {
              if ((e.key === 'Enter' || e.key === ',') && tagInput.trim()) {
                e.preventDefault();
                const newTag = tagInput.trim().replace(/^#/, '');
                if (newTag && !tags.includes(newTag)) setTags(prev => [...prev, newTag]);
                setTagInput('');
              }
            }}
          />
        </div>
      </div>

      {/* LLM 설정 모달 */}
      {showLLMSettings && (
        <div className="llm-settings-overlay" onClick={() => setShowLLMSettings(false)}>
          <div className="llm-settings-modal" onClick={e => e.stopPropagation()}>
            <div className="llm-settings-header">
              <h3>AI 생성 설정</h3>
              <button className="llm-settings-close" onClick={() => setShowLLMSettings(false)}>×</button>
            </div>
            <div className="llm-settings-body">
              <label>
                글투 (Tone)
                <select value={llmPrefs.tone} onChange={e => setLlmPrefs(p => ({ ...p, tone: e.target.value }))}>
                  <option value="casual">친근한 (Casual)</option>
                  <option value="formal">격식체 (Formal)</option>
                  <option value="poetic">시적인 (Poetic)</option>
                  <option value="humorous">유머러스 (Humorous)</option>
                </select>
              </label>
              <label>
                스타일 (Style)
                <select value={llmPrefs.style} onChange={e => setLlmPrefs(p => ({ ...p, style: e.target.value }))}>
                  <option value="blog">블로그</option>
                  <option value="diary">일기</option>
                  <option value="travel_guide">여행 가이드</option>
                </select>
              </label>
              <label>
                제목 언어 (Lang)
                <select value={llmPrefs.lang} onChange={e => setLlmPrefs(p => ({ ...p, lang: e.target.value }))}>
                  <option value="ko">한국어</option>
                  <option value="en">English</option>
                  <option value="ja">日本語</option>
                  <option value="zh">中文</option>
                  <option value="fr">Français</option>
                </select>
              </label>
              <label>
                추가 지침 (선택)
                <textarea
                  placeholder="AI에게 추가로 전달할 지침을 입력하세요..."
                  value={llmPrefs.stage3_extra || ''}
                  onChange={e => setLlmPrefs(p => ({ ...p, stage3_extra: e.target.value }))}
                  rows={3}
                />
              </label>
            </div>
            <div className="llm-settings-footer">
              <button className="llm-settings-cancel" onClick={() => setShowLLMSettings(false)}>취소</button>
              <button className="llm-settings-save" onClick={handleLLMSettingsSave} disabled={llmPrefsSaving}>
                {llmPrefsSaving ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 임시저장 draft 편집 중 안내 */}
      {isDraftPost && (
        <div className="draft-restore-banner">
          <span className="draft-restore-text">📝 임시저장된 게시글을 편집 중입니다.</span>
        </div>
      )}

      {/* 메인 콘텐츠 */}
      <div className="page-content">
        {isMobile && (
          <div className="tab-menu">
            <button className={`tab-button ${activeTab === 'image' ? 'active' : ''}`} onClick={() => setActiveTab('image')}>📷 사진</button>
            <button className={`tab-button ${activeTab === 'document' ? 'active' : ''}`} onClick={() => setActiveTab('document')}>📄 문서</button>
            <button className={`tab-button ${activeTab === 'map' ? 'active' : ''}`} onClick={() => setActiveTab('map')}>🗺️ 지도</button>
          </div>
        )}

        <div className="panels-container">
          <div
            className={`panel-wrapper left-panel ${isMobile && activeTab !== 'image' ? 'mobile-hidden' : ''}`}
            style={{ width: isMobile ? '100%' : `${leftWidth}%` }}
          >
            <ImagePanel />
          </div>

          {!isMobile && (
            <Resizer onResize={handleLeftResize} onStart={handleDragStart} onEnd={handleDragEnd} style={{ left: `${leftWidth}%` }} />
          )}

          <div
            className={`panel-wrapper center-panel ${isMobile && activeTab !== 'document' ? 'mobile-hidden' : ''}`}
            style={{ width: isMobile ? '100%' : `${centerWidth}%`, position: 'relative' }}
          >
            {isGeneratingContent && (
              <div className="ai-generating-overlay">
                <div className="ai-generating-spinner" />
                <p className="ai-generating-text">AI가 여행 기록을 작성하는 중...</p>
              </div>
            )}
            <DocumentPanel
              key={content ? 'has-content' : 'no-content'}
              initialContent={content}
              onContentChange={setContent}
              postId={isEditMode ? editPostId : null}
              onAIResult={handleAIResult}
            />
          </div>

          {!isMobile && (
            <Resizer onResize={handleRightResize} onStart={handleDragStart} onEnd={handleDragEnd} style={{ left: `${leftWidth + centerWidth}%` }} />
          )}

          <div
            className={`panel-wrapper right-panel ${isMobile && activeTab !== 'map' ? 'mobile-hidden' : ''}`}
            style={{ width: isMobile ? '100%' : `${rightWidth}%` }}
          >
            <MapPanel />
          </div>
        </div>
      </div>
    </div>
  );
};

export default CreateTripPage;
