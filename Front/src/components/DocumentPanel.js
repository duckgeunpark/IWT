import React, { useState } from 'react';
import '../styles/DocumentPanel.css';

const DocumentPanel = () => {
  const [documentContent, setDocumentContent] = useState(`계시물 / 결과물
레이아웃
글자 크기 강조
등등 여러가지
들어갈 공간`);

  const [isLLMProcessing, setIsLLMProcessing] = useState(false);

  const handleLLMGenerate = async () => {
    setIsLLMProcessing(true);
    try {
      // LLM 처리 로직
      console.log('LLM을 이용하여 게시물 수정');
      
      // 시뮬레이션 - 실제로는 백엔드 API 호출
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      setDocumentContent(`LLM 생성 결과:
      
여행 기록이 업데이트되었습니다.
로스앤젤레스 2025.05.02~2025.05.02 여행에 대한 
상세한 정보와 추천 내용이 포함되어 있습니다.

주요 장소:
- 계시물 위치 정보
- 레이아웃 최적화
- 글자 크기 및 강조 효과 적용
- 여행 경로 및 추천 정보

생성된 콘텐츠를 확인하고 필요에 따라 수정하세요.`);
    } catch (error) {
      console.error('LLM 처리 중 오류:', error);
    } finally {
      setIsLLMProcessing(false);
    }
  };

  const handleContentChange = (e) => {
    setDocumentContent(e.target.value);
  };

  const handleSave = () => {
    console.log('문서 저장:', documentContent);
    // 저장 로직 구현
  };

  const handlePreview = () => {
    console.log('미리보기');
    // 미리보기 로직 구현
  };

  return (
    <div className="document-panel">
      <div className="panel-header">
        <h3>게시물 / 결과물</h3>
        <div className="document-tools">
          <div className="formatting-tools">
            <button className="format-btn bold" title="굵게">B</button>
            <button className="format-btn italic" title="기울임">I</button>
            <button className="format-btn underline" title="밑줄">U</button>
            <button className="format-btn highlight" title="강조">H</button>
          </div>
          
          <div className="insert-tools">
            <button className="insert-btn">이미지 삽입</button>
            <button className="insert-btn">링크 추가</button>
          </div>
        </div>
      </div>

      <div className="document-content">
        <div className="content-area">
          <textarea
            className="document-textarea"
            value={documentContent}
            onChange={handleContentChange}
            placeholder="여행 기록을 작성하세요..."
            rows={20}
          />
        </div>

        <div className="document-actions">
          <button 
            className="llm-generate-btn"
            onClick={handleLLMGenerate}
            disabled={isLLMProcessing}
          >
            {isLLMProcessing ? (
              <>
                <span className="loading-spinner"></span>
                LLM 처리 중...
              </>
            ) : (
              'LLM을 이용하여 게시물 수정'
            )}
          </button>
        </div>
      </div>

      <div className="document-status">
        <span className="word-count">
          글자 수: {documentContent.length}
        </span>
        <span className="last-saved">
          마지막 저장: 방금 전
        </span>
      </div>
    </div>
  );
};

export default DocumentPanel;