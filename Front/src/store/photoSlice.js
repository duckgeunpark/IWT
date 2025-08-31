import { createSlice } from '@reduxjs/toolkit';

const photoSlice = createSlice({
  name: 'photos',
  initialState: {
    photos: [],
    locations: [],
    selectedPhotoId: null, // 선택된 사진 ID
    isLoading: false,
    error: null,
  },
  reducers: {
    addPhoto: (state, action) => {
      const { photo, gpsData, exifData } = action.payload;
      
      // 촬영 시간 추출 (EXIF에서)
      const captureTime = exifData?.backendData?.takenAtLocal || exifData?.backendData?.takenAtUTC || new Date().toISOString();
      const captureTimestamp = new Date(captureTime).getTime();
      
      const photoData = {
        id: Date.now() + Math.random(), // 임시 ID 생성
        file: photo.file,
        name: photo.name,
        size: photo.size,
        type: photo.type,
        preview: photo.preview,
        uploadTime: new Date().toISOString(),
        captureTime: captureTime, // 촬영 시간 추가
        captureTimestamp: captureTimestamp, // 정렬용 타임스탬프
        isActive: true, // 기본적으로 활성화
        color: `#${Math.floor(Math.random()*16777215).toString(16)}`, // 고유한 색상 저장
        gpsData,
        exifData,
      };

      state.photos.push(photoData);
      
      // 촬영 시간 순으로 정렬 (오래된 것부터)
      state.photos.sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));

      console.log('🔄 Redux addPhoto - 받은 GPS 데이터:', gpsData);
      console.log('📅 촬영 시간:', captureTime);

      // GPS 데이터가 있으면 locations 배열에도 추가
      if (gpsData && gpsData.lat && gpsData.lng) {
        // 촬영 시간을 한국어 형식으로 포맷팅
        const captureDate = new Date(captureTime);
        const formattedTime = captureDate.toLocaleString('ko-KR', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        });
        
        const locationData = {
          id: photoData.id,
          name: photo.name,
          coordinates: {
            lat: gpsData.lat,
            lng: gpsData.lng
          },
          color: photoData.color, // 사진의 고유 색상 사용
          time: formattedTime, // 촬영 시간으로 변경
          info: `${photo.name}에서 촬영`,
          photoId: photoData.id,
          captureTimestamp: captureTimestamp // 정렬용
        };
        
        state.locations.push(locationData);
        
        // 위치도 촬영 시간 순으로 정렬
        state.locations.sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));
        
        console.log('✅ Redux - locations 배열에 추가:', locationData);
        console.log('📍 현재 locations 배열 (정렬됨):', state.locations);
      } else {
        console.log('❌ GPS 데이터 없음 - locations에 추가되지 않음');
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
        
        // locations 배열도 업데이트
        const existingLocationIndex = state.locations.findIndex(l => l.photoId === photoId);
        
        if (gpsData && gpsData.lat && gpsData.lng) {
          const locationData = {
            id: photoId,
            name: photo.name,
            coordinates: {
              lat: gpsData.lat,
              lng: gpsData.lng
            },
            color: photo.color, // 사진의 고유 색상 사용
            time: new Date().toLocaleTimeString(),
            info: `${photo.name}에서 촬영`,
            photoId: photoId
          };
          
          if (existingLocationIndex >= 0) {
            state.locations[existingLocationIndex] = locationData;
          } else {
            state.locations.push(locationData);
          }
        } else {
          // GPS 데이터가 없으면 locations에서 제거
          if (existingLocationIndex >= 0) {
            state.locations.splice(existingLocationIndex, 1);
          }
        }
      }
    },
    
    clearPhotos: (state) => {
      state.photos = [];
      state.locations = [];
    },
    
    // 사진 활성화/비활성화 토글
    togglePhotoActive: (state, action) => {
      const photoId = action.payload;
      const photo = state.photos.find(p => p.id === photoId);
      
      if (photo) {
        photo.isActive = !photo.isActive;
        console.log(`🔄 사진 ${photo.isActive ? '활성화' : '비활성화'}:`, photo.name);
        
        // locations 배열 재구성 (활성화된 사진만)
        state.locations = state.photos
          .filter(p => p.isActive && p.gpsData && p.gpsData.lat && p.gpsData.lng)
          .map((p, index) => {
            const captureDate = new Date(p.captureTime);
            const formattedTime = captureDate.toLocaleString('ko-KR', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            });
            
            return {
              id: p.id,
              name: p.name,
              coordinates: {
                lat: p.gpsData.lat,
                lng: p.gpsData.lng
              },
              color: p.color, // 사진의 고유 색상 사용
              time: formattedTime,
              info: `${p.name}에서 촬영`,
              photoId: p.id,
              captureTimestamp: p.captureTimestamp
            };
          })
          .sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));
          
        console.log('📍 locations 재구성 완료:', state.locations);
      }
    },
    
    // 모든 사진 활성화
    activateAllPhotos: (state) => {
      state.photos.forEach(photo => {
        photo.isActive = true;
      });
      
      // locations 배열 재구성
      state.locations = state.photos
        .filter(p => p.gpsData && p.gpsData.lat && p.gpsData.lng)
        .map((p) => {
          const captureDate = new Date(p.captureTime);
          const formattedTime = captureDate.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
          });
          
          return {
            id: p.id,
            name: p.name,
            coordinates: {
              lat: p.gpsData.lat,
              lng: p.gpsData.lng
            },
            color: p.color, // 사진의 고유 색상 사용
            time: formattedTime,
            info: `${p.name}에서 촬영`,
            photoId: p.id,
            captureTimestamp: p.captureTimestamp
          };
        })
        .sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));
    },
    
    // 모든 사진 비활성화
    deactivateAllPhotos: (state) => {
      state.photos.forEach(photo => {
        photo.isActive = false;
      });
      state.locations = []; // 모든 위치 제거
    },
    
    setLoading: (state, action) => {
      state.isLoading = action.payload;
    },
    
    setError: (state, action) => {
      state.error = action.payload;
    },
    
    // 사진 선택
    setSelectedPhoto: (state, action) => {
      state.selectedPhotoId = action.payload;
    },
    
    // EXIF 데이터 업데이트
    updatePhotoExif: (state, action) => {
      const { photoId, updatedBackendData } = action.payload;
      const photo = state.photos.find(p => p.id === photoId);
      
      if (photo) {
        // EXIF 데이터 업데이트
        photo.exifData = {
          ...photo.exifData,
          backendData: updatedBackendData
        };
        
        // GPS 데이터도 업데이트
        if (updatedBackendData.gps) {
          photo.gpsData = updatedBackendData.gps;
        } else {
          photo.gpsData = null;
        }
        
        // 파일명도 업데이트
        if (updatedBackendData.originalFilename) {
          photo.name = updatedBackendData.originalFilename;
        }
        
        console.log('📝 Redux EXIF 업데이트 완료:', photo);
        
        // locations 배열도 GPS 데이터에 따라 재구성
        state.locations = state.photos
          .filter(p => p.isActive && p.gpsData && p.gpsData.lat && p.gpsData.lng)
          .map((p) => {
            const captureDate = new Date(p.captureTime);
            const formattedTime = captureDate.toLocaleString('ko-KR', {
              year: 'numeric',
              month: '2-digit',
              day: '2-digit',
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit'
            });
            
            return {
              id: p.id,
              name: p.name,
              coordinates: {
                lat: p.gpsData.lat,
                lng: p.gpsData.lng
              },
              color: p.color,
              time: formattedTime,
              info: `${p.name}에서 촬영`,
              photoId: p.id,
              captureTimestamp: p.captureTimestamp
            };
          })
          .sort((a, b) => (a.captureTimestamp || 0) - (b.captureTimestamp || 0));
          
        console.log('🗺️ locations 재구성 완료:', state.locations);
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
  setError 
} = photoSlice.actions;

export default photoSlice.reducer;