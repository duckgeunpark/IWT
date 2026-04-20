import React, { useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import exifr from 'exifr';
import { addPhotoToCluster, setRepresentativePhoto } from '../store/clusterSlice';
import { addPhoto, setLoading } from '../store/photoSlice';
import { fileStore } from '../store/fileStore';
import { compressImage, createThumbnail } from '../utils/imageCompressor';
import '../styles/ClusterPhotoPickerModal.css';

const ClusterPhotoPickerModal = ({ cluster, onClose }) => {
  const dispatch = useDispatch();
  const fileInputRef = useRef(null);
  const photos = useSelector(state => state.photos.photos);

  const clusterPhotos = photos.filter(p => cluster.photo_ids.includes(String(p.id)));

  const handleSelect = (photoId) => {
    dispatch(setRepresentativePhoto({ cluster_id: cluster.cluster_id, photo_id: String(photoId) }));
  };

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files);
    if (!files.length) return;

    dispatch(setLoading(true));
    try {
      for (const file of files) {
        if (!file.type.startsWith('image/')) continue;

        let gps = null;
        let captureTime = null;
        try {
          const exifData = await exifr.parse(file, { tiff: true, gps: true });
          const lat = exifData?.latitude || exifData?.GPSLatitude;
          const lng = exifData?.longitude || exifData?.GPSLongitude;
          if (lat && lng && !isNaN(lat) && !isNaN(lng)) {
            gps = { lat: parseFloat(lat), lng: parseFloat(lng) };
          }
          const dt = exifData?.DateTime || exifData?.DateTimeOriginal || exifData?.CreateDate;
          if (dt) captureTime = new Date(dt).toISOString();
        } catch (_) {}

        const compressed = await compressImage(file);
        const thumbnail = await createThumbnail(file);
        const photoId = Date.now() + Math.random();
        fileStore.set(photoId, compressed);

        const photoData = {
          id: photoId,
          name: file.name,
          size: compressed.size,
          type: compressed.type,
          preview: thumbnail,
          captureTime,
        };

        dispatch(addPhoto({ photo: photoData, gpsData: gps, exifData: null }));

        const strId = String(photoId);
        dispatch(addPhotoToCluster({ cluster_id: cluster.cluster_id, photo_id: strId }));
        dispatch(setRepresentativePhoto({ cluster_id: cluster.cluster_id, photo_id: strId }));
      }
    } finally {
      dispatch(setLoading(false));
      e.target.value = '';
    }
  };

  return (
    <div className="cpm-overlay" onClick={onClose}>
      <div className="cpm-modal" onClick={e => e.stopPropagation()}>
        <div className="cpm-header">
          <span className="cpm-title">{cluster.location_name} — 대표사진 선택</span>
          <button className="cpm-close" onClick={onClose}>✕</button>
        </div>

        <div className="cpm-grid">
          {clusterPhotos.length === 0 && (
            <p className="cpm-empty">이 클러스터에 사진이 없습니다.</p>
          )}
          {clusterPhotos.map(photo => {
            const isRep = String(photo.id) === String(cluster.representative_photo_id);
            return (
              <div
                key={photo.id}
                className={`cpm-item${isRep ? ' cpm-item--selected' : ''}`}
                onClick={() => handleSelect(photo.id)}
              >
                <img src={photo.preview} alt={photo.name} className="cpm-thumb" />
                {isRep && <span className="cpm-star">★</span>}
              </div>
            );
          })}
        </div>

        <div className="cpm-footer">
          <button className="cpm-upload-btn" onClick={handleUploadClick}>
            + 사진 추가
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />
          <button className="cpm-confirm-btn" onClick={onClose}>확인</button>
        </div>
      </div>
    </div>
  );
};

export default ClusterPhotoPickerModal;
