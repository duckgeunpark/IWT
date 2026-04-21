import React, { useState, useRef, useCallback } from 'react';
import { useSelector } from 'react-redux';
import MarkdownPreview from './MarkdownPreview';
import ClusterPhotoPickerModal from './ClusterPhotoPickerModal';
import { useToast } from './Toast';
import { apiClient } from '../services/apiClient';
import '../styles/DocumentPanel.css';

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

const parseSections = (content) => {
  const lines = content.split('\n');
  const sections = [];
  let current = { heading: null, body: [] };

  for (const line of lines) {
    const h2 = line.match(/^##\s+(.+)/);
    if (h2) {
      sections.push(current);
      current = { heading: h2[1].trim(), body: [] };
    } else {
      current.body.push(line);
    }
  }
  sections.push(current);
  return sections;
};

const DocumentPanel = ({ initialContent, initialTitle, onContentChange, postId, onAIResult }) => {
  const { photos, locations } = useSelector(state => state.photos);
  const clusters = useSelector(state => state.clusters.clusters);
  const toast = useToast();
  const [content, setContent] = useState(initialContent || SAMPLE_CONTENT);
  const [pickerCluster, setPickerCluster] = useState(null);

  const updateContent = useCallback((newContent) => {
    setContent(newContent);
    onContentChange?.(newContent);
  }, [onContentChange]);
  const [mode, setMode] = useState('preview');
  const [isLLMProcessing, setIsLLMProcessing] = useState(false);
  const textareaRef = useRef(null);

  /**
   * 텍스트 영역에 마크다운 서식 삽입
   */
  const insertFormatting = useCallback((prefix, suffix = prefix) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = content.substring(start, end);

    const newContent =
      content.substring(0, start) +
      prefix + (selected || '텍스트') + suffix +
      content.substring(end);

    updateContent(newContent);

    // 커서 위치 복원
    requestAnimationFrame(() => {
      textarea.focus();
      const newCursorPos = selected
        ? start + prefix.length + selected.length + suffix.length
        : start + prefix.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    });
  }, [content]);

  const handleBold = () => insertFormatting('**');
  const handleItalic = () => insertFormatting('*');
  const handleCode = () => insertFormatting('\n```\n', '\n```\n');
  const handleHeading = () => insertFormatting('## ', '\n');
  const handleLink = () => insertFormatting('[', '](url)');
  const handleImage = () => insertFormatting('![alt](', ')');
  const handleQuote = () => insertFormatting('> ', '\n');
  const handleList = () => insertFormatting('- ', '\n');
  const handleTable = () => {
    const table = '\n| 제목1 | 제목2 | 제목3 |\n|-------|-------|-------|\n| 내용 | 내용 | 내용 |\n';
    const textarea = textareaRef.current;
    if (!textarea) return;
    const pos = textarea.selectionStart;
    setContent(content.substring(0, pos) + table + content.substring(pos));
  };
  const handleHr = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const pos = textarea.selectionStart;
    setContent(content.substring(0, pos) + '\n---\n' + content.substring(pos));
  };

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

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
        textarea.selectionStart = start + markdownImage.length;
        textarea.selectionEnd = start + markdownImage.length;
      });
    } catch (err) {
      console.error("사진 드롭 처리 중 오류:", err);
    }
  }, [content, updateContent]);

  const handleLLMGenerate = async () => {
    if (photos.length === 0) {
      toast.warning('사진을 먼저 업로드해주세요.');
      return;
    }

    setIsLLMProcessing(true);
    try {
      // ── 편집 모드: 증분 ai-update 호출 ──
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

        const response = await apiClient.post(`/api/v1/posts/${postId}/ai-update`, photoData);
        if (response.markdown) {
          updateContent(response.markdown);
          onAIResult?.({ title: response.title, tags: response.tags });
        } else {
          throw new Error('ai-update 응답에 markdown 없음');
        }
        return;
      }

      // ── 신규 모드: 기존 generate-itinerary 흐름 유지 ──
      const photoData = photos.map(p => ({
        name: p.name,
        captureTime: p.captureTime,
        gps: p.gpsData,
      }));

      const locationData = locations.map(loc => ({
        name: loc.name,
        coordinates: loc.coordinates,
        time: loc.time,
      }));

      const response = await apiClient.post('/api/v1/llm/generate-itinerary', {
        route_data: {
          photos: photoData,
          locations: locationData,
          total_photos: photos.length,
        },
        user_preferences: { language: 'ko', format: 'markdown' },
      });

      if (response.success && response.itinerary) {
        updateContent(response.itinerary);
      } else {
        throw new Error(response.error_message || 'LLM 생성 실패');
      }
    } catch (error) {
      console.error('LLM 처리 중 오류:', error);
      toast.error('AI 생성에 실패했습니다. 다시 시도해주세요.');
    } finally {
      setIsLLMProcessing(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const textarea = textareaRef.current;
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      setContent(content.substring(0, start) + '  ' + content.substring(end));
      requestAnimationFrame(() => {
        textarea.setSelectionRange(start + 2, start + 2);
      });
    }
  };

  return (
    <div className="document-panel">
      <div className="panel-header">
        <h3>게시물 / 결과물</h3>
        <div className="mode-toggle">
          <button
            className={`mode-btn ${mode === 'edit' ? 'active' : ''}`}
            onClick={() => setMode('edit')}
          >
            편집
          </button>
          <button
            className={`mode-btn ${mode === 'preview' ? 'active' : ''}`}
            onClick={() => setMode('preview')}
          >
            미리보기
          </button>
        </div>
      </div>

      {mode === 'edit' && (
        <div className="markdown-toolbar">
          <button className="toolbar-btn" onClick={handleBold} title="굵게 (Ctrl+B)"><b>B</b></button>
          <button className="toolbar-btn" onClick={handleItalic} title="기울임 (Ctrl+I)"><i>I</i></button>
          <span className="toolbar-divider" />
          <button className="toolbar-btn" onClick={handleHeading} title="제목">H</button>
          <button className="toolbar-btn" onClick={handleQuote} title="인용">"</button>
          <button className="toolbar-btn" onClick={handleCode} title="코드 블록">&lt;/&gt;</button>
          <span className="toolbar-divider" />
          <button className="toolbar-btn" onClick={handleLink} title="링크">🔗</button>
          <button className="toolbar-btn" onClick={handleImage} title="이미지">🖼</button>
          <button className="toolbar-btn" onClick={handleTable} title="표">▦</button>
          <button className="toolbar-btn" onClick={handleList} title="목록">☰</button>
          <button className="toolbar-btn" onClick={handleHr} title="구분선">―</button>
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
                          <img
                            src={repPhoto.preview}
                            alt="대표사진"
                            className="dp-rep-thumb"
                          />
                        ) : (
                          <div className="dp-rep-thumb dp-rep-thumb--empty">📷</div>
                        )}
                        <button
                          className="dp-change-btn"
                          onClick={() => setPickerCluster(cluster)}
                        >
                          변경
                        </button>
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
              <>
                <span className="loading-spinner"></span>
                AI 생성 중...
              </>
            ) : (
              'LLM으로 여행 기록 생성'
            )}
          </button>
        </div>
        <div className="document-status">
          <span className="word-count">
            {content.length}자 · {content.split('\n').length}줄
          </span>
        </div>
      </div>

      {pickerCluster && (
        <ClusterPhotoPickerModal
          cluster={pickerCluster}
          onClose={() => setPickerCluster(null)}
        />
      )}
    </div>
  );
};

export default DocumentPanel;
