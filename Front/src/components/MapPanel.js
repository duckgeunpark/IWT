import React, { useState, useCallback, useRef, useEffect, Fragment } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { togglePhotoActive, setSelectedPhoto } from '../store/photoSlice';
import { Wrapper, Status } from "@googlemaps/react-wrapper";
import '../styles/MapPanel.css';

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

// Google Maps 컴포넌트
const GoogleMapComponent = ({ 
  center, 
  zoom, 
  locations, 
  selectedLocation, 
  onLocationSelect,
  mapType,
  onMapClick,
  showRoutes 
}) => {
  const ref = useRef();
  const [map, setMap] = useState();
  const [markers, setMarkers] = useState([]);
  const [routeLines, setRouteLines] = useState([]);

  useEffect(() => {
    if (ref.current && !map) {
      const newMap = new window.google.maps.Map(ref.current, {
        center,
        zoom,
        mapTypeId: mapType
      });
      
      // 지도 클릭 이벤트 리스너
      newMap.addListener("click", (e) => {
        if (onMapClick) {
          onMapClick(e.latLng.lat(), e.latLng.lng());
        }
      });

      setMap(newMap);
    }
  }, [ref, map, center, zoom, mapType, onMapClick]);

  // 지도 타입 변경
  useEffect(() => {
    if (map) {
      map.setMapTypeId(mapType);
    }
  }, [map, mapType]);

  // 마커 업데이트
  useEffect(() => {
    if (map) {
      // 기존 마커 제거
      markers.forEach(marker => marker.setMap(null));
      
      // 새 마커 생성
      const newMarkers = locations.map((location, index) => {
        const backgroundColor = location.color || '#ff6b6b';
        const textColor = getContrastColor(backgroundColor);
        
        const marker = new window.google.maps.Marker({
          position: location.coordinates,
          map: map,
          title: location.name,
          label: {
            text: (index + 1).toString(),
            color: textColor,
            fontSize: '12px',
            fontWeight: 'bold'
          },
          icon: {
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 12,
            fillColor: backgroundColor,
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2,
          }
        });

        // 마커 클릭 이벤트
        marker.addListener("click", () => {
          onLocationSelect(location.id);
        });

        // 선택된 마커 스타일 변경
        if (selectedLocation === location.id) {
          marker.setIcon({
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 14,
            fillColor: backgroundColor,
            fillOpacity: 1,
            strokeColor: '#ffff00',
            strokeWeight: 3,
          });
          
          marker.setLabel({
            text: (index + 1).toString(),
            color: textColor,
            fontSize: '14px',
            fontWeight: 'bold'
          });
        }

        return marker;
      });

      setMarkers(newMarkers);

      // 모든 마커가 보이도록 지도 범위 조정
      if (newMarkers.length > 1) {
        const bounds = new window.google.maps.LatLngBounds();
        locations.forEach(location => {
          bounds.extend(location.coordinates);
        });
        map.fitBounds(bounds);
      } else if (newMarkers.length === 1) {
        map.setCenter(locations[0].coordinates);
        map.setZoom(15);
      }
    }
  }, [map, locations, selectedLocation, onLocationSelect]);

  // 경로 선 업데이트
  useEffect(() => {
    if (map && locations.length >= 2) {
      // 기존 경로 선 제거
      routeLines.forEach(line => line.setMap(null));
      
      if (showRoutes) {
        // 새 경로 선 생성
        const newRouteLines = [];
        
        for (let i = 0; i < locations.length - 1; i++) {
          const routeLine = new window.google.maps.Polyline({
            path: [
              locations[i].coordinates,
              locations[i + 1].coordinates
            ],
            geodesic: true,
            strokeColor: locations[i].color || '#ff6b6b',
            strokeOpacity: 0.8,
            strokeWeight: 3,
            map: map
          });
          
          newRouteLines.push(routeLine);
        }
        
        setRouteLines(newRouteLines);
      } else {
        setRouteLines([]);
      }
    }
  }, [map, locations, showRoutes]);

  return <div ref={ref} style={{ width: "100%", height: "100%" }} />;
};

// 로딩 컴포넌트
const MapLoadingComponent = ({ status }) => {
  switch (status) {
    case Status.LOADING:
      return <div className="map-loading">지도를 불러오는 중...</div>;
    case Status.FAILURE:
      return <div className="map-error">지도를 불러올 수 없습니다. API 키를 확인해주세요.</div>;
    case Status.SUCCESS:
      return null;
    default:
      return <div className="map-loading">지도 초기화 중...</div>;
  }
};

const MapPanel = () => {
  const dispatch = useDispatch();
  const { locations, selectedPhotoId } = useSelector(state => state.photos);
  console.log('🗺️ MapPanel - Redux locations:', locations);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [mapType, setMapType] = useState('roadmap');
  const [center, setCenter] = useState({ lat: 37.566535, lng: 126.977969 }); // 서울 시청 기본 위치
  const [zoom, setZoom] = useState(12);
  const [showRoutes, setShowRoutes] = useState(true);

  // selectedPhotoId가 변경될 때 해당 위치를 선택
  useEffect(() => {
    if (selectedPhotoId) {
      const location = locations.find(loc => loc.id === selectedPhotoId);
      if (location) {
        setSelectedLocation(selectedPhotoId);
        setCenter(location.coordinates);
      }
    } else {
      setSelectedLocation(null);
    }
  }, [selectedPhotoId, locations]);

  const handleLocationSelect = useCallback((locationId) => {
    setSelectedLocation(locationId);
    const location = locations.find(loc => loc.id === locationId);
    if (location) {
      setCenter(location.coordinates);
      // 해당 사진을 선택 상태로 설정
      dispatch(setSelectedPhoto(locationId));
    }
  }, [locations, dispatch]);

  const handleMapClick = useCallback((lat, lng) => {
    console.log('지도 클릭:', lat, lng);
    // 새 위치 추가 로직을 여기에 구현할 수 있습니다
  }, []);

  const handleZoomIn = () => {
    setZoom(prevZoom => Math.min(prevZoom + 1, 20));
  };

  const handleZoomOut = () => {
    setZoom(prevZoom => Math.max(prevZoom - 1, 1));
  };

  const handleResetView = () => {
    if (locations.length > 0) {
      setCenter(locations[0].coordinates);
      setZoom(12);
    } else {
      // 기본 위치로 돌아가기 (서울 시청)
      setCenter({ lat: 37.566535, lng: 126.977969 });
      setZoom(12);
    }
  };

  const handleLocationEdit = (locationId) => {
    console.log('위치 편집:', locationId);
    // 위치 편집 로직
  };

  const handleLocationDelete = (locationId) => {
    console.log('위치 삭제:', locationId);
    // togglePhotoActive를 호출하여 해당 사진을 비활성화 (체크박스 해제와 동일)
    dispatch(togglePhotoActive(locationId));
  };

  // 환경변수에서 API 키 가져오기
  const apiKey = process.env.REACT_APP_GOOGLE_MAPS_API_KEY;

  if (!apiKey || apiKey === 'YOUR_GOOGLE_MAPS_API_KEY_HERE') {
    return (
      <div className="map-panel">
        <div className="panel-header">
          <h3>지도 및 위치 정보</h3>
        </div>
        <div className="map-container">
          <div className="map-error">
            <p>구글 맵스 API 키가 설정되지 않았습니다.</p>
            <p>.env 파일에 REACT_APP_GOOGLE_MAPS_API_KEY를 설정해주세요.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="map-panel">
      <div className="panel-header">
        <h3>지도 및 위치 정보</h3>
        <div className="map-controls">
          <button 
            className="map-control-btn"
            onClick={handleZoomIn}
            title="확대"
          >
            +
          </button>
          <button 
            className="map-control-btn"
            onClick={handleZoomOut}
            title="축소"
          >
            -
          </button>
          <button 
            className="map-control-btn"
            onClick={handleResetView}
            title="초기화"
          >
            ⌂
          </button>
        </div>
      </div>

      <div className="map-container">
        <Wrapper apiKey={apiKey} render={MapLoadingComponent}>
          <GoogleMapComponent
            center={center}
            zoom={zoom}
            locations={locations}
            selectedLocation={selectedLocation}
            onLocationSelect={handleLocationSelect}
            mapType={mapType}
            onMapClick={handleMapClick}
            showRoutes={showRoutes}
          />
        </Wrapper>
      </div>

      <div className="location-details">
        <h4>위치별 상세 정보</h4>
        <div className="location-list">
          {locations.map((location, index) => {
            console.log(`🗺️ Location ${index}:`, location.time);
            
            // 날짜 구분선 표시 여부 결정
            const shouldShowDaySeparator = index > 0 && (() => {
              // 다양한 날짜 형식 처리
              const extractDate = (timeString) => {
                if (!timeString) return null;
                
                // 한국어 형식: "2023. 08. 13. 오후 03:00:23"
                const koreanDateMatch = timeString.match(/(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\./);
                if (koreanDateMatch) {
                  const [, year, month, day] = koreanDateMatch;
                  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
                }
                
                // "YYYY-MM-DD HH:mm:ss" 형식
                if (timeString.includes('-') && timeString.includes(':')) {
                  return timeString.split(' ')[0];
                }
                
                // "YYYY:MM:DD HH:mm:ss" EXIF 형식
                if (timeString.includes(':')) {
                  const parts = timeString.split(' ');
                  if (parts[0] && parts[0].split(':').length === 3) {
                    return parts[0].replace(/:/g, '-');
                  }
                }
                
                // 다른 형식들도 시도
                const dateMatch = timeString.match(/(\d{4}[-:]\d{2}[-:]\d{2})/);
                if (dateMatch) {
                  return dateMatch[1].replace(/:/g, '-');
                }
                
                return timeString.split(' ')[0];
              };
              
              const currentDate = extractDate(location.time);
              const previousDate = extractDate(locations[index - 1].time);
              console.log(`🗺️ Date comparison ${index}: current=${currentDate}, previous=${previousDate}`);
              return currentDate && previousDate && currentDate !== previousDate;
            })();

            // 날짜로부터 일차 계산
            const getDayNumber = (locationIndex) => {
              if (locations.length === 0) return 1;
              
              // 같은 날짜 추출 함수 사용
              const extractDate = (timeString) => {
                if (!timeString) return null;
                
                // 한국어 형식: "2023. 08. 13. 오후 03:00:23"
                const koreanDateMatch = timeString.match(/(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\./);
                if (koreanDateMatch) {
                  const [, year, month, day] = koreanDateMatch;
                  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
                }
                
                if (timeString.includes('-') && timeString.includes(':')) {
                  return timeString.split(' ')[0];
                }
                
                if (timeString.includes(':')) {
                  const parts = timeString.split(' ');
                  if (parts[0] && parts[0].split(':').length === 3) {
                    return parts[0].replace(/:/g, '-');
                  }
                }
                
                const dateMatch = timeString.match(/(\d{4}[-:]\d{2}[-:]\d{2})/);
                if (dateMatch) {
                  return dateMatch[1].replace(/:/g, '-');
                }
                
                return timeString.split(' ')[0];
              };
              
              const firstDate = extractDate(locations[0].time);
              const currentDate = extractDate(locations[locationIndex].time);
              
              console.log(`🗺️ Day calculation: first=${firstDate}, current=${currentDate}`);
              
              if (!firstDate || !currentDate) return 1;
              
              const firstDateTime = new Date(firstDate);
              const currentDateTime = new Date(currentDate);
              const diffTime = currentDateTime - firstDateTime;
              const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
              
              console.log(`🗺️ Day number for index ${locationIndex}:`, diffDays + 1);
              
              return diffDays + 1;
            };

            const elements = [];
            
            // 첫 번째 항목일 때는 1일차 표시
            if (index === 0) {
              elements.push(
                <div key={`day-1`} className="day-separator">
                  <div className="day-separator-line"></div>
                  <span className="day-separator-text">1일차</span>
                  <div className="day-separator-line"></div>
                </div>
              );
            }
            
            // 날짜가 바뀌면 새 일차 표시
            if (shouldShowDaySeparator) {
              elements.push(
                <div key={`day-${getDayNumber(index)}`} className="day-separator">
                  <div className="day-separator-line"></div>
                  <span className="day-separator-text">{getDayNumber(index)}일차</span>
                  <div className="day-separator-line"></div>
                </div>
              );
            }
            
            // 위치 항목 추가
            elements.push(
              <div 
                key={location.id}
                className={`location-item ${selectedLocation === location.id ? 'selected' : ''}`}
                onClick={() => handleLocationSelect(location.id)}
              >
                <div 
                  className="location-marker-small" 
                  style={{ 
                    backgroundColor: location.color,
                    color: getContrastColor(location.color || '#ff6b6b')
                  }}
                >
                  {index + 1}
                </div>
                <div className="location-content">
                  <div className="location-header">
                    <span className="location-name">위치: {location.name}</span>
                  </div>
                  <div className="location-time">
                    촬영 시간: {location.time}
                  </div>
                  <div className="location-info">
                    정보: {location.info}
                  </div>
                  <div className="location-coordinates">
                    좌표: {location.coordinates.lat.toFixed(4)}, {location.coordinates.lng.toFixed(4)}
                  </div>
                </div>
                {selectedLocation === location.id && (
                  <div className="location-actions">
                    <button 
                      className="edit-location-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleLocationEdit(location.id);
                      }}
                    >
                      편집
                    </button>
                    <button 
                      className="delete-location-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleLocationDelete(location.id);
                      }}
                    >
                      삭제
                    </button>
                  </div>
                )}
              </div>
            );

            return elements;
          })}
        </div>
      </div>
    </div>
  );
};

export default MapPanel;