import React, { useState, useRef, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import exifr from 'exifr';
import { addPhoto, removePhoto, togglePhotoActive, activateAllPhotos, deactivateAllPhotos, setSelectedPhoto, updatePhotoExif, setLoading, setError } from '../store/photoSlice';
import DropdownMenu from './DropdownMenu';
import ExifEditModal from './ExifEditModal';
import '../styles/ImagePanel.css';

/**
 * 배경색의 밝기를 계산하여 적절한 글자색을 반환
 * @param {string} hexColor - 16진수 색상 코드 (예: #ff0000)
 * @returns {string} - 'white' 또는 'black'
 */
const getContrastColor = (hexColor) => {
  // #이 없으면 추가
  const color = hexColor.startsWith('#') ? hexColor.slice(1) : hexColor;
  
  // RGB로 변환
  const r = parseInt(color.substr(0, 2), 16);
  const g = parseInt(color.substr(2, 2), 16);
  const b = parseInt(color.substr(4, 2), 16);
  
  // 상대적 밝기 계산 (YIQ 공식)
  const brightness = ((r * 299) + (g * 587) + (b * 114)) / 1000;
  
  // 밝기가 128보다 크면 검은색, 작으면 흰색
  return brightness > 128 ? 'black' : 'white';
};

/**
 * 이미지 업로드 및 관리 패널
 * 기능: 다중 파일 업로드, 추가 업로드, 미리보기, 선택 관리
 */
const ImagePanel = () => {
  const dispatch = useDispatch();
  const { photos, locations, selectedPhotoId, isLoading } = useSelector(state => state.photos);
  
  // 이미지 관련 상태
  const [openMenuId, setOpenMenuId] = useState(null); // 열린 메뉴 ID
  const [menuPosition, setMenuPosition] = useState(null); // 메뉴 위치
  const [editingImageId, setEditingImageId] = useState(null); // 편집 중인 이미지 ID
  const [isEditModalOpen, setIsEditModalOpen] = useState(false); // 편집 모달 상태
  
  // 파일 입력 참조
  const fileInputRef = useRef(null);


  /**
   * 파일 해시 생성 (간단한 해시 함수)
   * @param {File} file - 파일 객체
   * @returns {Promise<string>} - 파일 해시
   */
  const generateFileHash = async (file) => {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  };

  /**
   * 시간대 오프셋 계산 (분 단위)
   * @param {Date} date - 날짜 객체
   * @returns {number} - 시간대 오프셋 (분)
   */
  const getTimezoneOffset = (date) => {
    return -date.getTimezoneOffset(); // JavaScript는 음수로 반환하므로 반전
  };

  /**
   * EXIF 정보 추출 및 백엔드용 데이터 포맷팅
   * @param {File} file - 이미지 파일
   * @returns {Promise<Object>} - 백엔드용 이미지 메타데이터
   */
  const extractExifData = async (file) => {
    try {
      // 파일 해시 생성
      const fileHash = await generateFileHash(file);
      
      // exifr을 사용해 EXIF 정보 추출 (모든 GPS 정보 포함)
      const exifData = await exifr.parse(file, {
        tiff: true,
        gps: true,
        // pick 제거하여 모든 EXIF 정보 읽기 (GPS 누락 방지)
      });

      // 촬영 시간 정보 처리
      const dateTime = exifData?.DateTime || exifData?.DateTimeOriginal || exifData?.CreateDate;
      let takenAtLocal = null;
      let takenAtUTC = null;
      let offsetMinutes = null;

      if (dateTime) {
        const parsedDate = new Date(dateTime);
        if (!isNaN(parsedDate.getTime())) {
          takenAtLocal = parsedDate.toISOString();
          offsetMinutes = getTimezoneOffset(parsedDate);
          
          // UTC 시간 계산
          const utcTime = new Date(parsedDate.getTime() - (offsetMinutes * 60000));
          takenAtUTC = utcTime.toISOString();
        }
      }

      // GPS 정보 처리 (전체 EXIF 디버깅)
      console.log('🌍 전체 EXIF 디버깅:', exifData);
      console.log('🌍 GPS 관련 필드들:', {
        latitude: exifData?.latitude,
        longitude: exifData?.longitude,
        GPSLatitude: exifData?.GPSLatitude,
        GPSLongitude: exifData?.GPSLongitude,
        GPSLatitudeRef: exifData?.GPSLatitudeRef,
        GPSLongitudeRef: exifData?.GPSLongitudeRef,
        GPSAltitude: exifData?.GPSAltitude,
        GPSHPositioningError: exifData?.GPSHPositioningError,
        allKeys: Object.keys(exifData || {}),
        gpsKeys: Object.keys(exifData || {}).filter(key => key.toLowerCase().includes('gps')),
        hasAnyGpsData: Object.keys(exifData || {}).some(key => key.toLowerCase().includes('gps'))
      });

      let gps = null;
      
      // 여러 GPS 필드 확인 (exifr 라이브러리의 다양한 GPS 표현)
      const lat = exifData?.latitude || exifData?.GPSLatitude;
      const lng = exifData?.longitude || exifData?.GPSLongitude;
      
      if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
        gps = {
          lat: parseFloat(lat),
          lng: parseFloat(lng),
        };
        
        // 고도 정보 (있는 경우)
        if (exifData?.GPSAltitude && !isNaN(exifData.GPSAltitude)) {
          gps.alt = parseFloat(exifData.GPSAltitude);
        }
        
        // GPS 정확도 (있는 경우)
        if (exifData?.GPSHPositioningError && !isNaN(exifData.GPSHPositioningError)) {
          gps.accuracyM = parseFloat(exifData.GPSHPositioningError);
        }
        
        console.log('✅ GPS 정보 추출 성공:', gps);
      } else {
        console.log('❌ GPS 정보 없음 또는 유효하지 않음');
        
        // 🧪 테스트용: GPS 정보가 없을 때 가짜 GPS 데이터 생성 (개발 중에만 사용)
        const useTestGps = window.confirm('GPS 정보가 없는 사진입니다. 테스트용 GPS 데이터를 사용하시겠습니까? (서울 시청 좌표)');
        
        if (useTestGps) {
          gps = {
            lat: 37.566535,
            lng: 126.977969,
            alt: 25.0,
            accuracyM: 10.0
          };
          console.log('🧪 테스트용 GPS 데이터 사용:', gps);
        }
      }

      // 백엔드 전송용 데이터 구조 (타입 변환 포함)
      const backendData = {
        id: Date.now() + Math.random(), // 임시 고유 ID
        fileHash,
        originalFilename: file.name,
        fileSizeBytes: file.size,
        mimeType: file.type,
        
        // 이미지 정보 (타입 안전성 보장)
        imageWidth: (() => {
          const width = exifData?.ExifImageWidth || exifData?.ImageWidth;
          return typeof width === 'number' ? width : (parseInt(width) || null);
        })(),
        imageHeight: (() => {
          const height = exifData?.ExifImageHeight || exifData?.ImageHeight;
          return typeof height === 'number' ? height : (parseInt(height) || null);
        })(),
        orientation: (() => {
          const orientation = exifData?.Orientation;
          return typeof orientation === 'number' ? orientation : (parseInt(orientation) || null);
        })(),
        colorSpace: (() => {
          const colorSpace = exifData?.ColorSpace;
          if (!colorSpace) return null;
          // ColorSpace가 숫자인 경우 적절한 문자열로 변환
          if (typeof colorSpace === 'number') {
            const colorSpaceMap = {
              1: 'sRGB',
              2: 'Adobe RGB',
              65535: 'Uncalibrated'
            };
            return colorSpaceMap[colorSpace] || `ColorSpace_${colorSpace}`;
          }
          return String(colorSpace);
        })(),
        
        // 시간 정보
        takenAtLocal,
        offsetMinutes,
        takenAtUTC,
        
        // GPS 정보
        gps,
        
        // 플래그 정보
        flags: {
          isEstimatedGeo: false // 현재는 실제 GPS 데이터만 사용
        }
      };

      // 콘솔용 상세 정보 (기존 로직 유지)
      const displayData = {
        hasExif: !!exifData,
        backendData, // 백엔드 전송용 데이터
        basic: {
          fileName: file.name,
          fileSize: `${(file.size / 1024 / 1024).toFixed(2)} MB`,
          fileType: file.type,
          fileHash: fileHash.substring(0, 16) + '...',
          lastModified: new Date(file.lastModified).toLocaleString('ko-KR')
        },
        image: {
          width: backendData.imageWidth || 'N/A',
          height: backendData.imageHeight || 'N/A',
          orientation: backendData.orientation || 'N/A',
          colorSpace: backendData.colorSpace || 'N/A'
        },
        time: {
          takenAtLocal: backendData.takenAtLocal || 'N/A',
          takenAtUTC: backendData.takenAtUTC || 'N/A',
          offsetMinutes: backendData.offsetMinutes || 'N/A'
        },
        location: gps ? {
          coordinates: `${gps.lat.toFixed(6)}, ${gps.lng.toFixed(6)}`,
          altitude: gps.alt || 'N/A',
          accuracy: gps.accuracyM || 'N/A'
        } : null,
        raw: exifData // 원본 EXIF 데이터
      };

      return displayData;

    } catch (error) {
      console.error('EXIF 추출 실패:', error);
      return { 
        hasExif: false, 
        error: error.message,
        message: 'EXIF 정보 추출 중 오류가 발생했습니다.',
        backendData: null
      };
    }
  };

  /**
   * EXIF 정보를 콘솔에 보기 좋게 출력
   * @param {Object} exifData - 포맷팅된 EXIF 데이터
   * @param {string} fileName - 파일명
   */
  const logExifToConsole = (exifData, fileName) => {
    console.group(`📷 EXIF 정보: ${fileName}`);
    
    if (!exifData.hasExif) {
      console.warn('❌', exifData.message);
      if (exifData.error) {
        console.error('오류:', exifData.error);
      }
      console.groupEnd();
      return;
    }

    // 백엔드 전송용 데이터
    console.group('🔄 백엔드 전송 데이터');
    console.log(exifData.backendData);
    console.groupEnd();

    // 기본 파일 정보
    console.group('📁 파일 정보');
    Object.entries(exifData.basic).forEach(([key, value]) => {
      console.log(`${key}: ${value}`);
    });
    console.groupEnd();

    // 이미지 정보
    console.group('🖼️ 이미지 정보');
    Object.entries(exifData.image).forEach(([key, value]) => {
      console.log(`${key}: ${value}`);
    });
    console.groupEnd();

    // 시간 정보
    console.group('⏰ 시간 정보');
    Object.entries(exifData.time).forEach(([key, value]) => {
      console.log(`${key}: ${value}`);
    });
    console.groupEnd();

    // 위치 정보 (있는 경우)
    if (exifData.location) {
      console.group('🌍 위치 정보 (GPS)');
      Object.entries(exifData.location).forEach(([key, value]) => {
        console.log(`${key}: ${value}`);
      });
      console.groupEnd();
    }

    // 원본 EXIF 데이터 (개발자용)
    console.group('🔍 전체 EXIF 데이터 (Raw)');
    console.log(exifData.raw);
    console.groupEnd();

    console.groupEnd();
  };

  /**
   * 백엔드로 이미지 메타데이터 전송
   * @param {Object} backendData - 백엔드 전송용 데이터
   * @returns {Promise<Object>} - API 응답
   */
  const sendImageMetadataToBackend = async (backendData) => {
    try {
      console.log('🚀 백엔드로 메타데이터 전송 중...', backendData);
      
      const response = await fetch('http://localhost:8000/api/v1/images/metadata', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(backendData)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('✅ 백엔드 응답:', result);
      return result;

    } catch (error) {
      console.error('❌ 백엔드 전송 실패:', error);
      throw error;
    }
  };

  /**
   * 파일 선택 다이얼로그 열기
   */
  const handleAddImage = () => {
    fileInputRef.current?.click();
  };

  /**
   * 파일 업로드 처리 (다중 파일 지원 + EXIF 정보 추출)
   * @param {Event} event - 파일 input change 이벤트
   */
  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files);
    
    if (files.length === 0) return;
    
    dispatch(setLoading(true));
    
    // 지원 파일 형식 확인
    const validFiles = files.filter(file => {
      const isImage = file.type.startsWith('image/');
      const isValidSize = file.size <= 10 * 1024 * 1024; // 10MB 제한
      
      if (!isImage) {
        alert(`${file.name}은(는) 이미지 파일이 아닙니다.`);
        return false;
      }
      if (!isValidSize) {
        alert(`${file.name}은(는) 파일 크기가 너무 큽니다. (최대 10MB)`);
        return false;
      }
      return true;
    });
    
    if (validFiles.length === 0) {
      dispatch(setLoading(false));
      return;
    }
    
    console.log(`🖼️ ${validFiles.length}개 이미지 업로드 시작...`);
    
    // 각 파일에 대해 EXIF 정보 추출 및 Redux store에 저장
    try {
      for (const file of validFiles) {
        const url = URL.createObjectURL(file); // 미리보기 URL
        
        // EXIF 정보 추출
        console.log(`📷 ${file.name} EXIF 정보 추출 중...`);
        const exifData = await extractExifData(file);
        
        // 콘솔에 EXIF 정보 출력
        logExifToConsole(exifData, file.name);
        
        // 사진 객체 생성
        const photoData = {
          file: file,
          name: file.name,
          size: file.size,
          type: file.type,
          preview: url
        };
        
        // Redux store에 사진과 GPS 데이터 저장
        console.log(`🗺️ ${file.name} GPS 데이터 Redux 저장:`, exifData.backendData?.gps);
        dispatch(addPhoto({
          photo: photoData,
          gpsData: exifData.backendData?.gps,
          exifData: exifData
        }));
        
        // 백엔드로 메타데이터 전송 (EXIF 정보가 있고 백엔드 데이터가 있는 경우)
        if (exifData.hasExif && exifData.backendData) {
          try {
            await sendImageMetadataToBackend(exifData.backendData);
          } catch (error) {
            console.warn(`⚠️ ${file.name} 메타데이터 백엔드 전송 실패:`, error.message);
          }
        }
      }
      
      dispatch(setLoading(false));
      
      // 파일 input 초기화 (같은 파일 재선택 가능하게)
      event.target.value = '';
      
      console.log(`✅ ${validFiles.length}개 이미지 업로드 완료 (Redux 저장)`);
    } catch (error) {
      console.error('❌ 이미지 업로드 중 오류:', error);
      dispatch(setError(error.message));
      dispatch(setLoading(false));
    }
  };

  const handleExploreImage = () => {
    // 이미지 탐색 로직
    console.log('이미지 탐색');
  };


  /**
   * 이미지 삭제
   * @param {number} imageId - 삭제할 이미지 ID
   */
  const handleImageDelete = (imageId) => {
    const imageToDelete = photos.find(img => img.id === imageId);
    
    if (imageToDelete && window.confirm(`"${imageToDelete.name}"을(를) 삭제하시겠습니까?`)) {
      // URL 메모리 해제
      if (imageToDelete.preview) {
        URL.revokeObjectURL(imageToDelete.preview);
      }
      
      // Redux store에서 제거
      dispatch(removePhoto(imageId));
      
      console.log(`🗑️ 이미지 삭제됨: ${imageToDelete.name}`);
    }
  };


  /**
   * 사진 활성화/비활성화 토글
   * @param {number} photoId - 사진 ID
   */
  const handlePhotoToggle = (photoId) => {
    dispatch(togglePhotoActive(photoId));
  };

  /**
   * 전체 활성화/비활성화 토글
   */
  const handleToggleAll = () => {
    const allActive = photos.every(photo => photo.isActive);
    
    if (allActive) {
      dispatch(deactivateAllPhotos());
    } else {
      dispatch(activateAllPhotos());
    }
  };

  /**
   * 메뉴 토글 - 완전한 position: fixed 좌표 계산
   * @param {number} imageId - 이미지 ID
   * @param {Event} event - 클릭 이벤트
   */
  const handleMenuToggle = (imageId, event) => {
    console.log('🔄 메뉴 토글:', imageId, '현재 열린 메뉴:', openMenuId);
    
    // 기존 메뉴가 열려있으면 먼저 닫고
    if (openMenuId === imageId) {
      console.log('📴 메뉴 닫기:', imageId);
      setOpenMenuId(null);
      setMenuPosition(null);
    } else {
      // 버튼의 위치 계산 (뷰포트 기준)
      const buttonRect = event.currentTarget.getBoundingClientRect();
      const menuWidth = 80;
      const menuHeight = 68;
      
      let left = buttonRect.left - menuWidth - 5; // 버튼 왼쪽에 5px 간격
      let top = buttonRect.top - 15; // 버튼보다 더 위로
      
      // 좌우 경계 체크
      if (left < 10) {
        left = buttonRect.right + 5; // 화면 왼쪽 경계에 닿으면 버튼 오른쪽으로
      }
      if (left + menuWidth > window.innerWidth - 10) {
        left = window.innerWidth - menuWidth - 10; // 화면 우측에서 10px 띄움
      }
      
      // 상하 경계 체크
      if (top + menuHeight > window.innerHeight - 10) {
        top = buttonRect.top - menuHeight - 4; // 버튼 위로 표시
      }
      if (top < 10) {
        top = 10; // 최소 10px 위에서 표시
      }
      
      const menuPos = { left, top };
      console.log('📍 메뉴 위치 계산 (개선):', menuPos, 'viewport:', { width: window.innerWidth, height: window.innerHeight });
      
      setMenuPosition(menuPos);
      setOpenMenuId(imageId);
    }
  };

  /**
   * 메뉴 닫기
   */
  const handleMenuClose = () => {
    setOpenMenuId(null);
    setMenuPosition(null);
  };

  /**
   * 사진 편집 - EXIF 편집 모달 열기
   * @param {number} imageId - 이미지 ID
   */
  const handleImageEdit = (imageId) => {
    console.log('사진 편집 시작:', imageId);
    setEditingImageId(imageId);
    setIsEditModalOpen(true);
  };

  /**
   * EXIF 편집 모달 닫기
   */
  const handleEditModalClose = () => {
    setIsEditModalOpen(false);
    setEditingImageId(null);
  };

  /**
   * EXIF 편집 저장 완료
   * @param {number} imageId - 이미지 ID
   * @param {Object} updatedBackendData - 업데이트된 백엔드 데이터
   */
  const handleExifSave = (imageId, updatedBackendData) => {
    console.log('✅ EXIF 저장 완료:', imageId, updatedBackendData);
    
    // Redux store에 업데이트된 EXIF 데이터 반영
    dispatch(updatePhotoExif({ 
      photoId: imageId, 
      updatedBackendData: updatedBackendData 
    }));
    
    console.log('🔄 Redux store EXIF 업데이트 완료');
    alert('EXIF 정보가 성공적으로 업데이트되었습니다!');
  };

  /**
   * 이미지 클릭 시 해당 이미지를 선택 상태로 설정
   * @param {number} imageId - 클릭된 이미지 ID
   */
  const handleImageClick = (imageId) => {
    dispatch(setSelectedPhoto(imageId));
  };

  /**
   * 패널 클릭 시 선택 해제
   */
  const handlePanelClick = (e) => {
    // 이미지 아이템이 아닌 곳을 클릭했을 때만 선택 해제
    if (e.target === e.currentTarget || e.target.closest('.image-section')) {
      dispatch(setSelectedPhoto(null));
      // 메뉴도 닫기
      setOpenMenuId(null);
      setMenuPosition(null);
    }
  };

  return (
    <>
      <div className="image-panel" onClick={handlePanelClick}>
        <div className="panel-header">
          <h3>사진 정보 / 위치 정보</h3>
        </div>
        
        {/* 숨겨진 파일 입력 */}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileUpload}
        />
        
        <div className="action-buttons">
          <button className="add-btn" onClick={handleAddImage}>
            📸 이미지 추가 ({photos.length})
          </button>
          <button className="explore-btn" onClick={handleExploreImage}>탐색</button>
        </div>

        <div className="image-section">
          <div className="section-header">
            <h4>업로드된 이미지</h4>
            {photos.length > 0 && (
              <div className="header-controls">
                <span className="active-count">
                  {photos.filter(p => p.isActive).length}/{photos.length}
                </span>
                <button className="toggle-all-btn" onClick={handleToggleAll}>
                  {photos.every(photo => photo.isActive) ? '🚫 전체 비활성화' : '✅ 전체 활성화'}
                </button>
              </div>
            )}
          </div>
          
          {photos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📷</div>
              <p>아직 업로드된 이미지가 없습니다.</p>
              <button className="upload-first-btn" onClick={handleAddImage}>
                첫 번째 이미지 업로드하기
              </button>
            </div>
          ) : (
            <div className="image-list">
              {photos.map((image, photoIndex) => {
                // 활성화된 사진들 중에서의 순서 계산
                const activatedPhotos = photos.filter(p => p.isActive);
                const mapOrderNumber = activatedPhotos.findIndex(p => p.id === image.id) + 1;
                
                // 해당 사진의 위치 정보 찾기 (색상을 위해)
                const location = locations.find(loc => loc.photoId === image.id);
                
                return (
                  <div 
                    key={image.id} 
                    className={`image-item ${selectedPhotoId === image.id ? 'selected' : ''}`} 
                    onClick={(e) => {
                      e.stopPropagation();
                      handleImageClick(image.id);
                    }}
                  >
                    {/* 이미지 미리보기 */}
                    <div className="image-preview">
                      <img src={image.preview} alt={image.name} />
                      {/* 지도 순서 번호 표시 (활성화된 경우) */}
                      {image.isActive && mapOrderNumber > 0 && (
                        <div 
                          className="map-order-number" 
                          style={{ 
                            backgroundColor: location?.color || '#007bff',
                            color: getContrastColor(location?.color || '#007bff')
                          }}
                        >
                          {mapOrderNumber}
                        </div>
                      )}
                    </div>
                    
                    <div className="image-info">
                      <span className="image-name" title={image.name}>{image.name}</span>
                    </div>
                  
                  {/* 지도 표시 체크박스 (점점점 메뉴 바로 왼쪽) */}
                  <div className="map-checkbox">
                    <input
                      type="checkbox"
                      id={`map-${image.id}`}
                      checked={image.isActive}
                      onChange={() => handlePhotoToggle(image.id)}
                      title="지도에 표시"
                    />
                  </div>
                  
                  {/* 점점점 메뉴 */}
                  <div className="menu-container">
                    <button 
                      className="menu-btn"
                      onClick={(e) => handleMenuToggle(image.id, e)}
                      title="메뉴"
                    >
                      ⋮
                    </button>
                  </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* 드롭다운 메뉴 컴포넌트 */}
      <DropdownMenu
        isOpen={openMenuId !== null}
        position={menuPosition}
        onClose={handleMenuClose}
        items={[
          {
            icon: '✏️',
            label: '편집',
            color: '#2563eb',
            hoverColor: '#dbeafe',
            onClick: () => handleImageEdit(openMenuId)
          },
          {
            icon: '🗑️',
            label: '삭제',
            color: '#dc2626',
            hoverColor: '#fee2e2',
            onClick: () => handleImageDelete(openMenuId)
          }
        ]}
      />

      {/* EXIF 편집 모달 */}
      <ExifEditModal
        isOpen={isEditModalOpen}
        onClose={handleEditModalClose}
        imageData={editingImageId ? photos.find(photo => photo.id === editingImageId) : null}
        onSave={handleExifSave}
      />
    </>
  );
};

export default ImagePanel;