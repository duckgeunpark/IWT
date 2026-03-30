import React, { useState, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import exifr from 'exifr';
import { addPhoto, removePhoto, togglePhotoActive, activateAllPhotos, deactivateAllPhotos, setSelectedPhoto, updatePhotoExif, setLoading, setError } from '../store/photoSlice';
import DropdownMenu from './DropdownMenu';
import ExifEditModal from './ExifEditModal';
import getContrastColor from '../utils/getContrastColor';
import { apiClient } from '../services/apiClient';
import '../styles/ImagePanel.css';

/**
 * 이미지 업로드 및 관리 패널
 */
const ImagePanel = () => {
  const dispatch = useDispatch();
  const { photos, locations, selectedPhotoId } = useSelector(state => state.photos);

  const [openMenuId, setOpenMenuId] = useState(null);
  const [menuPosition, setMenuPosition] = useState(null);
  const [editingImageId, setEditingImageId] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const fileInputRef = useRef(null);

  const generateFileHash = async (file) => {
    const buffer = await file.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  };

  const getTimezoneOffset = (date) => {
    return -date.getTimezoneOffset();
  };

  const extractExifData = async (file) => {
    try {
      const fileHash = await generateFileHash(file);

      const exifData = await exifr.parse(file, {
        tiff: true,
        gps: true,
      });

      const dateTime = exifData?.DateTime || exifData?.DateTimeOriginal || exifData?.CreateDate;
      let takenAtLocal = null;
      let takenAtUTC = null;
      let offsetMinutes = null;

      if (dateTime) {
        const parsedDate = new Date(dateTime);
        if (!isNaN(parsedDate.getTime())) {
          takenAtLocal = parsedDate.toISOString();
          offsetMinutes = getTimezoneOffset(parsedDate);
          const utcTime = new Date(parsedDate.getTime() - (offsetMinutes * 60000));
          takenAtUTC = utcTime.toISOString();
        }
      }

      let gps = null;
      const lat = exifData?.latitude || exifData?.GPSLatitude;
      const lng = exifData?.longitude || exifData?.GPSLongitude;

      if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
        gps = {
          lat: parseFloat(lat),
          lng: parseFloat(lng),
        };

        if (exifData?.GPSAltitude && !isNaN(exifData.GPSAltitude)) {
          gps.alt = parseFloat(exifData.GPSAltitude);
        }
        if (exifData?.GPSHPositioningError && !isNaN(exifData.GPSHPositioningError)) {
          gps.accuracyM = parseFloat(exifData.GPSHPositioningError);
        }
      }

      const backendData = {
        id: Date.now() + Math.random(),
        fileHash,
        originalFilename: file.name,
        fileSizeBytes: file.size,
        mimeType: file.type,
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
          if (typeof colorSpace === 'number') {
            const colorSpaceMap = { 1: 'sRGB', 2: 'Adobe RGB', 65535: 'Uncalibrated' };
            return colorSpaceMap[colorSpace] || `ColorSpace_${colorSpace}`;
          }
          return String(colorSpace);
        })(),
        takenAtLocal,
        offsetMinutes,
        takenAtUTC,
        gps,
        flags: { isEstimatedGeo: false }
      };

      return {
        hasExif: !!exifData,
        backendData,
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
        raw: exifData
      };

    } catch (error) {
      return {
        hasExif: false,
        error: error.message,
        message: 'EXIF 정보 추출 중 오류가 발생했습니다.',
        backendData: null
      };
    }
  };

  const sendImageMetadataToBackend = async (backendData) => {
    return apiClient.post('/api/v1/images/metadata', backendData);
  };

  const handleAddImage = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length === 0) return;

    dispatch(setLoading(true));

    const validFiles = files.filter(file => {
      const isImage = file.type.startsWith('image/');
      const isValidSize = file.size <= 10 * 1024 * 1024;

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

    try {
      for (const file of validFiles) {
        const url = URL.createObjectURL(file);
        const exifData = await extractExifData(file);

        const photoData = {
          file: file,
          name: file.name,
          size: file.size,
          type: file.type,
          preview: url
        };

        dispatch(addPhoto({
          photo: photoData,
          gpsData: exifData.backendData?.gps,
          exifData: exifData
        }));

        if (exifData.hasExif && exifData.backendData) {
          try {
            await sendImageMetadataToBackend(exifData.backendData);
          } catch (_) {
            // 백엔드 전송 실패는 로컬 작업에 영향 없음
          }
        }
      }

      dispatch(setLoading(false));
      event.target.value = '';
    } catch (error) {
      dispatch(setError(error.message));
      dispatch(setLoading(false));
    }
  };

  const handleExploreImage = () => {
    // TODO: 이미지 탐색 로직
  };

  const handleImageDelete = (imageId) => {
    const imageToDelete = photos.find(img => img.id === imageId);

    if (imageToDelete && window.confirm(`"${imageToDelete.name}"을(를) 삭제하시겠습니까?`)) {
      if (imageToDelete.preview) {
        URL.revokeObjectURL(imageToDelete.preview);
      }
      dispatch(removePhoto(imageId));
    }
  };

  const handlePhotoToggle = (photoId) => {
    dispatch(togglePhotoActive(photoId));
  };

  const handleToggleAll = () => {
    const allActive = photos.every(photo => photo.isActive);
    if (allActive) {
      dispatch(deactivateAllPhotos());
    } else {
      dispatch(activateAllPhotos());
    }
  };

  const handleMenuToggle = (imageId, event) => {
    if (openMenuId === imageId) {
      setOpenMenuId(null);
      setMenuPosition(null);
    } else {
      const buttonRect = event.currentTarget.getBoundingClientRect();
      const menuWidth = 80;
      const menuHeight = 68;

      let left = buttonRect.left - menuWidth - 5;
      let top = buttonRect.top - 15;

      if (left < 10) left = buttonRect.right + 5;
      if (left + menuWidth > window.innerWidth - 10) left = window.innerWidth - menuWidth - 10;
      if (top + menuHeight > window.innerHeight - 10) top = buttonRect.top - menuHeight - 4;
      if (top < 10) top = 10;

      setMenuPosition({ left, top });
      setOpenMenuId(imageId);
    }
  };

  const handleMenuClose = () => {
    setOpenMenuId(null);
    setMenuPosition(null);
  };

  const handleImageEdit = (imageId) => {
    setEditingImageId(imageId);
    setIsEditModalOpen(true);
  };

  const handleEditModalClose = () => {
    setIsEditModalOpen(false);
    setEditingImageId(null);
  };

  const handleExifSave = (imageId, updatedBackendData) => {
    dispatch(updatePhotoExif({
      photoId: imageId,
      updatedBackendData: updatedBackendData
    }));
    alert('EXIF 정보가 성공적으로 업데이트되었습니다!');
  };

  const handleImageClick = (imageId) => {
    dispatch(setSelectedPhoto(imageId));
  };

  const handlePanelClick = (e) => {
    if (e.target === e.currentTarget || e.target.closest('.image-section')) {
      dispatch(setSelectedPhoto(null));
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

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: 'none' }}
          onChange={handleFileUpload}
          aria-label="이미지 파일 선택"
        />

        <div className="action-buttons">
          <button className="add-btn" onClick={handleAddImage} aria-label="이미지 추가">
            이미지 추가 ({photos.length})
          </button>
          <button className="explore-btn" onClick={handleExploreImage} aria-label="이미지 탐색">탐색</button>
        </div>

        <div className="image-section">
          <div className="section-header">
            <h4>업로드된 이미지</h4>
            {photos.length > 0 && (
              <div className="header-controls">
                <span className="active-count">
                  {photos.filter(p => p.isActive).length}/{photos.length}
                </span>
                <button className="toggle-all-btn" onClick={handleToggleAll} aria-label="전체 토글">
                  {photos.every(photo => photo.isActive) ? '전체 비활성화' : '전체 활성화'}
                </button>
              </div>
            )}
          </div>

          {photos.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon" aria-hidden="true">📷</div>
              <p>아직 업로드된 이미지가 없습니다.</p>
              <button className="upload-first-btn" onClick={handleAddImage}>
                첫 번째 이미지 업로드하기
              </button>
            </div>
          ) : (
            <div className="image-list" role="list">
              {photos.map((image) => {
                const activatedPhotos = photos.filter(p => p.isActive);
                const mapOrderNumber = activatedPhotos.findIndex(p => p.id === image.id) + 1;
                const location = locations.find(loc => loc.photoId === image.id);

                return (
                  <div
                    key={image.id}
                    className={`image-item ${selectedPhotoId === image.id ? 'selected' : ''}`}
                    role="listitem"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleImageClick(image.id);
                    }}
                  >
                    <div className="image-preview">
                      <img src={image.preview} alt={image.name} />
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

                    <div className="map-checkbox">
                      <input
                        type="checkbox"
                        id={`map-${image.id}`}
                        checked={image.isActive}
                        onChange={() => handlePhotoToggle(image.id)}
                        aria-label={`${image.name} 지도에 표시`}
                      />
                    </div>

                    <div className="menu-container">
                      <button
                        className="menu-btn"
                        onClick={(e) => handleMenuToggle(image.id, e)}
                        aria-label={`${image.name} 메뉴`}
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
