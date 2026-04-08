import React, { useState, useEffect } from 'react';
import { apiClient } from '../services/apiClient';
import '../styles/ExifEditModal.css';

/**
 * EXIF 정보 편집 모달 컴포넌트
 * @param {Object} props
 * @param {boolean} props.isOpen - 모달 열림/닫힘 상태
 * @param {Function} props.onClose - 모달 닫기 콜백
 * @param {Object} props.imageData - 편집할 이미지 데이터
 * @param {Function} props.onSave - 저장 콜백
 */
const ExifEditModal = ({ isOpen, onClose, imageData, onSave }) => {
  
  // 편집 가능한 EXIF 데이터 상태
  const [editData, setEditData] = useState({
    originalFilename: '',
    takenAtLocal: '',
    offsetMinutes: 0,
    imageWidth: '',
    imageHeight: '',
    orientation: '',
    colorSpace: ''
  });
  
  const [isSaving, setIsSaving] = useState(false);
  
  // 모달이 열릴 때 이미지 데이터로 초기화
  useEffect(() => {
    if (isOpen && imageData && imageData.exifData?.backendData) {
      const backendData = imageData.exifData.backendData;
      
      setEditData({
        originalFilename: backendData.originalFilename || imageData.name,
        takenAtLocal: backendData.takenAtLocal ?
          new Date(backendData.takenAtLocal).toISOString().slice(0, 16) : '',
        offsetMinutes: backendData.offsetMinutes || 0,
        imageWidth: backendData.imageWidth?.toString() || '',
        imageHeight: backendData.imageHeight?.toString() || '',
        orientation: backendData.orientation?.toString() || '',
        colorSpace: backendData.colorSpace || ''
      });
    }
  }, [isOpen, imageData]);
  
  // ESC 키로 모달 닫기
  useEffect(() => {
    if (!isOpen) return;
    
    const handleEscKey = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscKey);
    return () => {
      document.removeEventListener('keydown', handleEscKey);
    };
  }, [isOpen, onClose]);
  
  /**
   * 입력 값 변경 핸들러
   * @param {string} field - 필드명
   * @param {string} value - 새 값
   */
  const handleInputChange = (field, value) => {
    setEditData(prev => ({
      ...prev,
      [field]: value
    }));
  };
  
  /**
   * 저장 처리
   */
  const handleSave = async () => {
    try {
      setIsSaving(true);
      
      // 편집된 데이터 준비 (GPS는 읽기 전용으로 원본 유지)
      const updatedBackendData = {
        ...imageData.exifData.backendData,
        originalFilename: editData.originalFilename,
        takenAtLocal: editData.takenAtLocal ? new Date(editData.takenAtLocal).toISOString() : null,
        offsetMinutes: parseInt(editData.offsetMinutes) || 0,
        takenAtUTC: editData.takenAtLocal && editData.offsetMinutes ?
          new Date(new Date(editData.takenAtLocal).getTime() - (parseInt(editData.offsetMinutes) * 60000)).toISOString() : null,
        imageWidth: editData.imageWidth ? parseInt(editData.imageWidth) : null,
        imageHeight: editData.imageHeight ? parseInt(editData.imageHeight) : null,
        orientation: editData.orientation ? parseInt(editData.orientation) : null,
        colorSpace: editData.colorSpace || null
      };
      
      // 백엔드로 업데이트된 메타데이터 전송
      await apiClient.put(`/api/v1/images/metadata/${updatedBackendData.id}`, updatedBackendData);

      // 부모 컴포넌트에 저장 완료 알림
      onSave(imageData.id, updatedBackendData);
      
      // 모달 닫기
      onClose();
      
    } catch (error) {
      alert('EXIF 데이터 저장에 실패했습니다: ' + error.message);
    } finally {
      setIsSaving(false);
    }
  };
  
  if (!isOpen) return null;
  
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="exif-edit-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>📷 EXIF 정보 편집</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <div className="modal-content">
          <div className="form-section">
            <h3>📁 기본 정보</h3>
            <div className="form-group">
              <label>파일명:</label>
              <input
                type="text"
                value={editData.originalFilename}
                onChange={(e) => handleInputChange('originalFilename', e.target.value)}
                placeholder="파일명을 입력하세요"
              />
            </div>
          </div>
          
          <div className="form-section">
            <h3>🌍 GPS 위치 정보 (읽기 전용)</h3>
            {imageData?.exifData?.backendData?.gps ? (
              <div className="gps-readonly">
                <div className="gps-readonly-row">
                  <span className="gps-label">위도</span>
                  <span className="gps-value">{imageData.exifData.backendData.gps.lat?.toFixed(6)}</span>
                  <span className="gps-label">경도</span>
                  <span className="gps-value">{imageData.exifData.backendData.gps.lng?.toFixed(6)}</span>
                </div>
                {imageData.exifData.backendData.gps.alt && (
                  <div className="gps-readonly-row">
                    <span className="gps-label">고도</span>
                    <span className="gps-value">{imageData.exifData.backendData.gps.alt?.toFixed(1)}m</span>
                  </div>
                )}
                <p className="gps-note">GPS 좌표는 사진의 EXIF에서 자동 추출됩니다.</p>
              </div>
            ) : (
              <p className="gps-empty">이 사진에는 GPS 정보가 없습니다.</p>
            )}
          </div>
          
          <div className="form-section">
            <h3>⏰ 시간 정보</h3>
            <div className="form-row">
              <div className="form-group">
                <label>촬영 시간:</label>
                <input
                  type="datetime-local"
                  value={editData.takenAtLocal}
                  onChange={(e) => handleInputChange('takenAtLocal', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>시간대 오프셋 (분):</label>
                <input
                  type="number"
                  value={editData.offsetMinutes}
                  onChange={(e) => handleInputChange('offsetMinutes', e.target.value)}
                  placeholder="예: 540 (UTC+9)"
                />
              </div>
            </div>
          </div>
          
          <div className="form-section">
            <h3>🖼️ 이미지 정보</h3>
            <div className="form-row">
              <div className="form-group">
                <label>가로 (px):</label>
                <input
                  type="number"
                  value={editData.imageWidth}
                  onChange={(e) => handleInputChange('imageWidth', e.target.value)}
                  placeholder="픽셀"
                />
              </div>
              <div className="form-group">
                <label>세로 (px):</label>
                <input
                  type="number"
                  value={editData.imageHeight}
                  onChange={(e) => handleInputChange('imageHeight', e.target.value)}
                  placeholder="픽셀"
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>회전 정보:</label>
                <select
                  value={editData.orientation}
                  onChange={(e) => handleInputChange('orientation', e.target.value)}
                >
                  <option value="">선택 없음</option>
                  <option value="1">정상 (1)</option>
                  <option value="3">180도 회전 (3)</option>
                  <option value="6">시계방향 90도 (6)</option>
                  <option value="8">반시계방향 90도 (8)</option>
                </select>
              </div>
              <div className="form-group">
                <label>색공간:</label>
                <input
                  type="text"
                  value={editData.colorSpace}
                  onChange={(e) => handleInputChange('colorSpace', e.target.value)}
                  placeholder="예: sRGB"
                />
              </div>
            </div>
          </div>
        </div>
        
        <div className="modal-footer">
          <button className="cancel-btn" onClick={onClose} disabled={isSaving}>
            취소
          </button>
          <button className="save-btn" onClick={handleSave} disabled={isSaving}>
            {isSaving ? '저장 중...' : '💾 저장'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExifEditModal;