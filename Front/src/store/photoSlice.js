import { createSlice } from '@reduxjs/toolkit';

const formatTime = (captureTime) => {
  const captureDate = new Date(captureTime);
  return captureDate.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
};

const buildLocations = (photos) => {
  return photos
    .filter(p => p.isActive && p.gpsData && p.gpsData.lat && p.gpsData.lng)
    .map((p) => ({
      id: p.id,
      name: p.name,
      coordinates: { lat: p.gpsData.lat, lng: p.gpsData.lng },
      color: p.color,
      time: formatTime(p.captureTime),
      info: `${p.name}에서 촬영`,
      photoId: p.id,
      captureTimestamp: p.captureTimestamp
    }))
    .sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));
};

const photoSlice = createSlice({
  name: 'photos',
  initialState: {
    photos: [],
    locations: [],
    selectedPhotoId: null,
    isLoading: false,
    error: null,
    uploadProgress: { current: 0, total: 0 },
  },
  reducers: {
    addPhoto: (state, action) => {
      const { photo, gpsData, exifData } = action.payload;

      const captureTime = exifData?.backendData?.takenAtLocal || exifData?.backendData?.takenAtUTC || new Date().toISOString();
      const captureTimestamp = new Date(captureTime).getTime();

      const photoData = {
        id: photo.id || (Date.now() + Math.random()),
        name: photo.name,
        size: photo.size,
        type: photo.type,
        preview: photo.preview,
        uploadTime: new Date().toISOString(),
        captureTime,
        captureTimestamp,
        isActive: true,
        color: `#${Math.floor(Math.random()*16777215).toString(16).padStart(6, '0')}`,
        gpsData,
        exifData,
      };

      state.photos.push(photoData);
      state.photos.sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));

      if (gpsData && gpsData.lat && gpsData.lng) {
        state.locations.push({
          id: photoData.id,
          name: photo.name,
          coordinates: { lat: gpsData.lat, lng: gpsData.lng },
          color: photoData.color,
          time: formatTime(captureTime),
          info: `${photo.name}에서 촬영`,
          photoId: photoData.id,
          captureTimestamp,
        });
        state.locations.sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));
      }
    },

    removePhoto: (state, action) => {
      const photoId = action.payload;
      state.photos = state.photos.filter(photo => photo.id !== photoId);
      state.locations = state.locations.filter(location => location.photoId !== photoId);
    },

    updatePhotoGPS: (state, action) => {
      const { photoId, gpsData } = action.payload;
      const photo = state.photos.find(p => p.id === photoId);

      if (photo) {
        photo.gpsData = gpsData;
        state.locations = buildLocations(state.photos);
      }
    },

    clearPhotos: (state) => {
      state.photos = [];
      state.locations = [];
    },

    togglePhotoActive: (state, action) => {
      const photoId = action.payload;
      const photo = state.photos.find(p => p.id === photoId);

      if (photo) {
        photo.isActive = !photo.isActive;
        state.locations = buildLocations(state.photos);
      }
    },

    activateAllPhotos: (state) => {
      state.photos.forEach(photo => { photo.isActive = true; });
      state.locations = buildLocations(state.photos);
    },

    deactivateAllPhotos: (state) => {
      state.photos.forEach(photo => { photo.isActive = false; });
      state.locations = [];
    },

    setLoading: (state, action) => {
      state.isLoading = action.payload;
    },

    setError: (state, action) => {
      state.error = action.payload;
    },

    setUploadProgress: (state, action) => {
      state.uploadProgress = action.payload;
    },

    setSelectedPhoto: (state, action) => {
      state.selectedPhotoId = action.payload;
    },

    updatePhotoExif: (state, action) => {
      const { photoId, updatedBackendData } = action.payload;
      const photo = state.photos.find(p => p.id === photoId);

      if (photo) {
        photo.exifData = { ...photo.exifData, backendData: updatedBackendData };
        photo.gpsData = updatedBackendData.gps || null;

        if (updatedBackendData.originalFilename) {
          photo.name = updatedBackendData.originalFilename;
        }

        state.locations = buildLocations(state.photos);
      }
    }
  }
});

export const {
  addPhoto,
  removePhoto,
  updatePhotoGPS,
  clearPhotos,
  togglePhotoActive,
  activateAllPhotos,
  deactivateAllPhotos,
  setSelectedPhoto,
  updatePhotoExif,
  setLoading,
  setError,
  setUploadProgress
} = photoSlice.actions;

export default photoSlice.reducer;
