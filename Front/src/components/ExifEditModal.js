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
    // 기본 이미지 정보
    originalFilename: '',
    
    // GPS 정보 (편집 가능)
    gpsLat: '',
    gpsLng: '',
    gpsAlt: '',
    gpsAccuracyM: '',
    
    // 시간 정보 (편집 가능)
    takenAtLocal: '',
    offsetMinutes: 0,
    
    // 기타 메타데이터
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
        
        // GPS 정보
        gpsLat: backendData.gps?.lat?.toString() || '',
        gpsLng: backendData.gps?.lng?.toString() || '',
        gpsAlt: backendData.gps?.alt?.toString() || '',
        gpsAccuracyM: backendData.gps?.accuracyM?.toString() || '',
        
        // 시간 정보
        takenAtLocal: backendData.takenAtLocal ? 
          new Date(backendData.takenAtLocal).toISOString().slice(0, 16) : '',
        offsetMinutes: backendData.offsetMinutes || 0,
        
        // 기타 정보
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
      
      // 편집된 데이터 준비
      const updatedBackendData = {
        ...imageData.exifData.backendData,
        originalFilename: editData.originalFilename,
        
        // GPS 정보 업데이트
        gps: {
          lat: editData.gpsLat ? parseFloat(editData.gpsLat) : null,
          lng: editData.gpsLng ? parseFloat(editData.gpsLng) : null,
          alt: editData.gpsAlt ? parseFloat(editData.gpsAlt) : null,
          accuracyM: editData.gpsAccuracyM ? parseFloat(editData.gpsAccuracyM) : null
        },
        
        // 시간 정보 업데이트
        takenAtLocal: editData.takenAtLocal ? new Date(editData.takenAtLocal).toISOString() : null,
        offsetMinutes: parseInt(editData.offsetMinutes) || 0,
        takenAtUTC: editData.takenAtLocal && editData.offsetMinutes ? 
          new Date(new Date(editData.takenAtLocal).getTime() - (parseInt(editData.offsetMinutes) * 60000)).toISOString() : null,
        
        // 이미지 정보 업데이트
        imageWidth: editData.imageWidth ? parseInt(editData.imageWidth) : null,
        imageHeight: editData.imageHeight ? parseInt(editData.imageHeight) : null,
        orientation: editData.orientation ? parseInt(editData.orientation) : null,
        colorSpace: editData.colorSpace || null
      };
      
      // GPS 정보가 유효하지 않으면 null로 설정
      if (!updatedBackendData.gps.lat || !updatedBackendData.gps.lng) {
        updatedBackendData.gps = null;
      }
      
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
            <h3>🌍 GPS 위치 정보</h3>
            <div className="form-row">
              <div className="form-group">
                <label>위도 (Latitude):</label>
                <input
                  type="number"
                  step="any"
                  value={editData.gpsLat}
                  onChange={(e) => handleInputChange('gpsLat', e.target.value)}
                  placeholder="예: 37.566535"
                />
              </div>
              <div className="form-group">
                <label>경도 (Longitude):</label>
                <input
                  type="number"
                  step="any"
                  value={editData.gpsLng}
                  onChange={(e) => handleInputChange('gpsLng', e.target.value)}
                  placeholder="예: 126.977969"
                />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>고도 (Altitude, m):</label>
                <input
                  type="number"
                  step="any"
                  value={editData.gpsAlt}
                  onChange={(e) => handleInputChange('gpsAlt', e.target.value)}
                  placeholder="미터 단위"
                />
              </div>
              <div className="form-group">
                <label>GPS 정확도 (m):</label>
                <input
                  type="number"
                  step="any"
                  value={editData.gpsAccuracyM}
                  onChange={(e) => handleInputChange('gpsAccuracyM', e.target.value)}
                  placeholder="미터 단위"
                />
              </div>
            </div>
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