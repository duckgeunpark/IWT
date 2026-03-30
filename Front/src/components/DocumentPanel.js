import React, { useState, useRef, useCallback } from 'react';
import MarkdownPreview from './MarkdownPreview';
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

const DocumentPanel = () => {
  const [content, setContent] = useState(SAMPLE_CONTENT);
  const [mode, setMode] = useState('preview'); // 'edit' | 'preview'
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

    setContent(newContent);

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

  const handleLLMGenerate = async () => {
    setIsLLMProcessing(true);
    try {
      // TODO: 실제 백엔드 API 호출로 교체
      await new Promise(resolve => setTimeout(resolve, 2000));

      setContent(prev => prev + `\n\n## AI 생성 콘텐츠

> 이 내용은 LLM이 자동 생성한 여행 기록입니다.

사진의 위치 정보와 시간 정보를 바탕으로 분석한 결과입니다.

### 주요 장소
- 장소 정보가 사진 메타데이터로부터 추출됩니다
- 경로 추천이 자동으로 생성됩니다

### 여행 요약
사진을 업로드하면 더 정확한 기록이 생성됩니다.
`);
    } catch (error) {
      console.error('LLM 처리 중 오류:', error);
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
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="마크다운으로 여행 기록을 작성하세요..."
          />
        ) : (
          <div className="markdown-preview-area">
            <MarkdownPreview content={content} />
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
    </div>
  );
};

export default DocumentPanel;
