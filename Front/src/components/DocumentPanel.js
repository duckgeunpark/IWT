import React, { useState, useRef, useCallback } from 'react';
import { useSelector } from 'react-redux';
import MarkdownPreview from './MarkdownPreview';
import ClusterPhotoPickerModal from './ClusterPhotoPickerModal';
import { useToast } from './Toast';
import { apiClient } from '../services/apiClient';
import '../styles/DocumentPanel.css';

// ── 구 마크다운 기반 폴백 에디터 ────────────────────────────────────────────
const SAMPLE_CONTENT = `# 여행 기록

여행 사진을 업로드하고 기록을 작성하세요.

## 일정

| 날짜 | 장소 | 메모 |
|------|------|------|
| 1일차 | - | - |

## 메모

> 사진을 업로드하면 자동으로 위치와 시간 정보가 추출됩니다.

---

*LLM 버튼을 눌러 AI가 여행 기록을 자동 생성하도록 할 수 있습니다.*
`;

// ── 블록 타입별 레이블 ───────────────────────────────────────────────────────
const BLOCK_LABELS = {
  title:          '제목',
  itinerary:      '일정표',
  cluster_photos: '사진',
  cluster_text:   '여행 글',
  conclusion:     '마무리',
  user_insert:    '메모',
};

// ── 블록 상태 배지 ───────────────────────────────────────────────────────────
const StatusBadge = ({ block }) => {
  if (block.locked) return <span className="block-badge locked">🔒 잠김</span>;
  if (block.user_content !== null && block.user_content !== undefined)
    return <span className="block-badge modified">✏️ 수정됨</span>;
  if (block.ai_content !== null && block.ai_content !== undefined)
    return <span className="block-badge ai">✅ AI 생성</span>;
  return null;
};

// ── 단일 편집 가능 블록 ──────────────────────────────────────────────────────
const EditableBlock = ({ block, photos, onUpdate, onToggleLock }) => {
  const [editing, setEditing] = useState(false);
  const displayContent = block.user_content ?? block.ai_content ?? '';

  const handleSave = (newText) => {
    onUpdate(block.block_id, { user_content: newText || null });
    setEditing(false);
  };

  const handleReset = () => {
    onUpdate(block.block_id, { user_content: null });
    setEditing(false);
  };

  if (block.block_type === 'cluster_photos') {
    const clusterPhotos = photos.filter(p => String(p.dbClusterId) === String(block.cluster_id));
    return (
      <div className="block-photos">
        <div className="photo-grid">
          {clusterPhotos.map(p => (
            <img key={p.id} src={p.preview} alt={p.name} className="block-photo-thumb" />
          ))}
          {clusterPhotos.length === 0 && (
            <div className="block-photo-empty">📷 사진 없음</div>
          )}
        </div>
      </div>
    );
  }

  if (block.block_type === 'title') {
    return (
      <div className="block-title-wrap">
        {editing ? (
          <input
            className="block-title-input"
            defaultValue={displayContent}
            autoFocus
            onBlur={(e) => handleSave(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSave(e.target.value)}
          />
        ) : (
          <h1 className="block-title-text" onClick={() => !block.locked && setEditing(true)}>
            {displayContent || '제목 없음'}
          </h1>
        )}
      </div>
    );
  }

  return (
    <div className="block-text-wrap">
      <div className="block-text-header">
        <StatusBadge block={block} />
        <div className="block-text-actions">
          {!block.locked && (
            <button className="block-action-btn" onClick={() => setEditing(e => !e)}>
              {editing ? '닫기' : '편집'}
            </button>
          )}
          {!block.locked && block.user_content !== null && (
            <button className="block-action-btn reset" onClick={handleReset}>↩ 원본</button>
          )}
          <button
            className="block-action-btn lock"
            onClick={() => onToggleLock(block.block_id)}
            title={block.locked ? '잠금 해제' : '잠금 (재생성 제외)'}
          >
            {block.locked ? '🔓' : '🔒'}
          </button>
        </div>
      </div>
      {editing && !block.locked ? (
        <textarea
          className="block-textarea"
          defaultValue={displayContent}
          rows={6}
          onBlur={(e) => handleSave(e.target.value)}
        />
      ) : (
        <MarkdownPreview content={displayContent} />
      )}
    </div>
  );
};

// ── 메인 DocumentPanel ───────────────────────────────────────────────────────
const DocumentPanel = ({
  initialContent,
  initialBlocks,
  initialTitle,
  onContentChange,
  onBlocksChange,
  postId,
  onAIResult,
}) => {
  const { photos } = useSelector(state => state.photos);
  const toast = useToast();

  // ── 블록 모드 vs 마크다운 모드 결정 ──────────────────────────────────────
  const hasBlocks = Array.isArray(initialBlocks) && initialBlocks.length > 0;

  // ── 마크다운 모드 상태 ────────────────────────────────────────────────────
  const [content, setContent] = useState(initialContent || SAMPLE_CONTENT);
  const [mode, setMode] = useState('preview');
  const textareaRef = useRef(null);
  const [pickerCluster, setPickerCluster] = useState(null);
  const clusters = useSelector(state => state.clusters.clusters);

  // ── 블록 모드 상태 ────────────────────────────────────────────────────────
  const [blocks, setBlocks] = useState(initialBlocks || []);
  const [isLLMProcessing, setIsLLMProcessing] = useState(false);

  const updateContent = useCallback((newContent) => {
    setContent(newContent);
    onContentChange?.(newContent);
  }, [onContentChange]);

  const updateBlocks = useCallback((newBlocks) => {
    setBlocks(newBlocks);
    onBlocksChange?.(newBlocks);
  }, [onBlocksChange]);

  // ── 블록 업데이트 (단일 블록 필드 변경) ──────────────────────────────────
  const handleBlockUpdate = useCallback((blockId, changes) => {
    setBlocks(prev => {
      const next = prev.map(b => b.block_id === blockId ? { ...b, ...changes } : b);
      onBlocksChange?.(next);
      return next;
    });
  }, [onBlocksChange]);

  const handleToggleLock = useCallback((blockId) => {
    setBlocks(prev => {
      const next = prev.map(b => b.block_id === blockId ? { ...b, locked: !b.locked } : b);
      onBlocksChange?.(next);
      return next;
    });
  }, [onBlocksChange]);

  // ── AI 재생성 (블록 모드: regenerate 엔드포인트) ──────────────────────────
  const handleBlockRegenerate = useCallback(async (options = {}) => {
    if (photos.length === 0) {
      toast.warning('사진을 먼저 업로드해주세요.');
      return;
    }
    if (!postId) return;

    setIsLLMProcessing(true);
    try {
      const photoData = photos.map(p => ({
        file_key: p.fileKey || '',
        file_name: p.name,
        file_size: p.size,
        content_type: p.type,
        _lat: p.gpsData?.lat || null,
        _lon: p.gpsData?.lng || null,
        location_info: p.locationInfo || null,
      }));

      const response = await apiClient.postStream(`/api/v1/posts/${postId}/regenerate`, {
        photos: photoData,
        regenerate_title: options.regenerateTitle || false,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = JSON.parse(line.slice(6));
          if (data.step === 'error') throw new Error(data.message);
          if (data.step === 'done') {
            // 재생성 완료 → 게시글 데이터 새로 로드
            const updated = await apiClient.get(`/api/v1/posts/${postId}`);
            if (updated.blocks) {
              updateBlocks(updated.blocks);
            }
            const stats = data.cache_stats;
            if (stats) {
              const parts = [
                stats.hit > 0 && `${stats.hit}개 섹션 보존`,
                stats.miss > 0 && `${stats.miss}개 섹션 업데이트`,
              ].filter(Boolean);
              if (parts.length) toast.success(parts.join(', '));
            }
          }
        }
      }
    } catch (error) {
      console.error('AI 재생성 오류:', error);
      toast.error('AI 재생성에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setIsLLMProcessing(false);
    }
  }, [photos, postId, toast, updateBlocks]);

  // ── AI 생성 (마크다운 모드: 기존 ai-update) ──────────────────────────────
  const handleLLMGenerate = async () => {
    if (photos.length === 0) {
      toast.warning('사진을 먼저 업로드해주세요.');
      return;
    }

    setIsLLMProcessing(true);
    try {
      if (postId) {
        const photoData = photos.map(p => ({
          file_key: p.fileKey || '',
          file_name: p.name,
          file_size: p.size,
          content_type: p.type,
          _lat: p.gpsData?.lat || null,
          _lon: p.gpsData?.lng || null,
          location_info: p.locationInfo || null,
        }));

        const response = await apiClient.post(`/api/v1/posts/${postId}/ai-update`, {
          photos: photoData,
          current_content: content,
        });
        if (response.markdown) {
          updateContent(response.markdown);
          onAIResult?.({ title: response.title, tags: response.tags });
          const stats = response.cache_stats;
          if (stats) {
            const parts = [
              stats.miss > 0 && `${stats.miss}개 섹션 업데이트`,
              stats.new_sections > 0 && `${stats.new_sections}개 새 섹션 추가`,
            ].filter(Boolean);
            if (parts.length) toast.success(parts.join(', '));
          }
        }
      } else {
        const photoData = photos.map(p => ({
          name: p.name, captureTime: p.captureTime, gps: p.gpsData,
        }));
        const locationData = (useSelector ? [] : []);
        const response = await apiClient.post('/api/v1/llm/generate-itinerary', {
          route_data: { photos: photoData, locations: locationData, total_photos: photos.length },
          user_preferences: { language: 'ko', format: 'markdown' },
        });
        if (response.success && response.itinerary) updateContent(response.itinerary);
        else throw new Error(response.error_message || 'LLM 생성 실패');
      }
    } catch (error) {
      console.error('LLM 처리 중 오류:', error);
      toast.error('AI 생성에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setIsLLMProcessing(false);
    }
  };

  // ── 마크다운 툴바 헬퍼 ───────────────────────────────────────────────────
  const insertFormatting = useCallback((prefix, suffix = prefix) => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = content.substring(start, end);
    const newContent =
      content.substring(0, start) + prefix + (selected || '텍스트') + suffix + content.substring(end);
    updateContent(newContent);
    requestAnimationFrame(() => {
      textarea.focus();
      const pos = selected
        ? start + prefix.length + selected.length + suffix.length
        : start + prefix.length;
      textarea.setSelectionRange(pos, pos);
    });
  }, [content, updateContent]);

  const handleKeyDown = (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = textareaRef.current;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      setContent(content.substring(0, start) + '  ' + content.substring(end));
      requestAnimationFrame(() => textarea.setSelectionRange(start + 2, start + 2));
    }
  };

  const handleDragOver = useCallback((e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; }, []);
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    try {
      const data = e.dataTransfer.getData('application/json');
      if (!data) return;
      const photo = JSON.parse(data);
      const markdownImage = `!${photo.name}\n`;
      const textarea = textareaRef.current;
      if (!textarea) return;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const newContent = content.substring(0, start) + markdownImage + content.substring(end);
      updateContent(newContent);
      requestAnimationFrame(() => {
        textarea.focus();
        textarea.setSelectionRange(start + markdownImage.length, start + markdownImage.length);
      });
    } catch (err) {
      console.error('사진 드롭 처리 중 오류:', err);
    }
  }, [content, updateContent]);

  // ════════════════════════════════════════════════════════════════════════════
  // ── 블록 모드 렌더링 ──────────────────────────────────────────────────────
  // ════════════════════════════════════════════════════════════════════════════
  if (hasBlocks) {
    const editableBlocks = blocks.filter(b => b.block_type !== 'cluster_photos');
    const hasUserEdits = blocks.some(b => b.user_content !== null && b.user_content !== undefined);

    return (
      <div className="document-panel">
        <div className="panel-header">
          <h3>게시물 / 결과물</h3>
          <div className="block-editor-badge">블록 편집 모드</div>
        </div>

        <div className="document-content block-editor">
          {blocks.map(block => (
            <div key={block.block_id} className={`block-wrapper block-type-${block.block_type}`}>
              {block.block_type !== 'title' && block.block_type !== 'cluster_photos' && (
                <div className="block-type-label">{BLOCK_LABELS[block.block_type] || block.block_type}</div>
              )}
              <EditableBlock
                block={block}
                photos={photos}
                onUpdate={handleBlockUpdate}
                onToggleLock={handleToggleLock}
              />
            </div>
          ))}
        </div>

        <div className="document-footer">
          <div className="document-actions">
            <button
              className="llm-generate-btn"
              onClick={() => handleBlockRegenerate()}
              disabled={isLLMProcessing}
            >
              {isLLMProcessing ? (
                <><span className="loading-spinner"></span>AI 재생성 중...</>
              ) : (
                'AI로 재생성'
              )}
            </button>
          </div>
          <div className="document-status">
            <span className="word-count">
              {blocks.length}개 블록
              {hasUserEdits && <span className="edit-badge"> · ✏️ 편집됨</span>}
            </span>
          </div>
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════════════════════════════════════════
  // ── 마크다운 모드 렌더링 (구 포맷 폴백) ──────────────────────────────────
  // ════════════════════════════════════════════════════════════════════════════
  const parseSections = (md) => {
    const lines = md.split('\n');
    const sections = [];
    let current = { heading: null, body: [] };
    for (const line of lines) {
      const h2 = line.match(/^##\s+(.+)/);
      if (h2) { sections.push(current); current = { heading: h2[1].trim(), body: [] }; }
      else current.body.push(line);
    }
    sections.push(current);
    return sections;
  };

  return (
    <div className="document-panel">
      <div className="panel-header">
        <h3>게시물 / 결과물</h3>
        <div className="mode-toggle">
          <button className={`mode-btn ${mode === 'edit' ? 'active' : ''}`} onClick={() => setMode('edit')}>편집</button>
          <button className={`mode-btn ${mode === 'preview' ? 'active' : ''}`} onClick={() => setMode('preview')}>미리보기</button>
        </div>
      </div>

      {mode === 'edit' && (
        <div className="markdown-toolbar">
          <button className="toolbar-btn" onClick={() => insertFormatting('**')} title="굵게"><b>B</b></button>
          <button className="toolbar-btn" onClick={() => insertFormatting('*')} title="기울임"><i>I</i></button>
          <span className="toolbar-divider" />
          <button className="toolbar-btn" onClick={() => insertFormatting('## ', '\n')} title="제목">H</button>
          <button className="toolbar-btn" onClick={() => insertFormatting('> ', '\n')} title="인용">"</button>
          <button className="toolbar-btn" onClick={() => insertFormatting('\n```\n', '\n```\n')} title="코드">&lt;/&gt;</button>
          <span className="toolbar-divider" />
          <button className="toolbar-btn" onClick={() => insertFormatting('[', '](url)')} title="링크">🔗</button>
          <button className="toolbar-btn" onClick={() => insertFormatting('![alt](', ')')} title="이미지">🖼</button>
          <button className="toolbar-btn" onClick={() => {
            const pos = textareaRef.current?.selectionStart || 0;
            setContent(content.substring(0, pos) + '\n| 제목1 | 제목2 | 제목3 |\n|-------|-------|-------|\n| 내용 | 내용 | 내용 |\n' + content.substring(pos));
          }} title="표">▦</button>
          <button className="toolbar-btn" onClick={() => insertFormatting('- ', '\n')} title="목록">☰</button>
          <button className="toolbar-btn" onClick={() => {
            const pos = textareaRef.current?.selectionStart || 0;
            setContent(content.substring(0, pos) + '\n---\n' + content.substring(pos));
          }} title="구분선">―</button>
        </div>
      )}

      <div className="document-content">
        {mode === 'edit' ? (
          <textarea
            ref={textareaRef}
            className="document-textarea"
            value={content}
            onChange={(e) => updateContent(e.target.value)}
            onKeyDown={handleKeyDown}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            placeholder="마크다운으로 여행 기록을 작성하세요..."
          />
        ) : (
          <div className="markdown-preview-area">
            {clusters.length > 0 ? (
              parseSections(content).map((section, idx) => {
                const cluster = clusters.find(c => c.section_heading === section.heading);
                const repPhoto = cluster
                  ? photos.find(p => String(p.id) === String(cluster.representative_photo_id))
                  : null;
                const sectionMd = section.heading
                  ? `## ${section.heading}\n${section.body.join('\n')}`
                  : section.body.join('\n');
                return (
                  <div key={idx} className="dp-section">
                    {cluster && (
                      <div className="dp-section-cluster-bar">
                        {repPhoto ? (
                          <img src={repPhoto.preview} alt="대표사진" className="dp-rep-thumb" />
                        ) : (
                          <div className="dp-rep-thumb dp-rep-thumb--empty">📷</div>
                        )}
                        <button className="dp-change-btn" onClick={() => setPickerCluster(cluster)}>변경</button>
                      </div>
                    )}
                    <MarkdownPreview content={sectionMd} />
                  </div>
                );
              })
            ) : (
              <MarkdownPreview content={content} />
            )}
          </div>
        )}
      </div>

      <div className="document-footer">
        <div className="document-actions">
          <button
            className="llm-generate-btn"
            onClick={handleLLMGenerate}
            disabled={isLLMProcessing}
          >
            {isLLMProcessing ? (
              <><span className="loading-spinner"></span>AI 생성 중...</>
            ) : (
              'LLM으로 여행 기록 생성'
            )}
          </button>
        </div>
        <div className="document-status">
          <span className="word-count">{content.length}자 · {content.split('\n').length}줄</span>
        </div>
      </div>

      {pickerCluster && (
        <ClusterPhotoPickerModal cluster={pickerCluster} onClose={() => setPickerCluster(null)} />
      )}
    </div>
  );
};

export default DocumentPanel;
