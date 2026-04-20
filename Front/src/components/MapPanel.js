import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { togglePhotoActive, setSelectedPhoto, updatePhotoGPS } from '../store/photoSlice';
import { Wrapper, Status } from "@googlemaps/react-wrapper";
import { apiClient } from '../services/apiClient';
import getContrastColor from '../utils/getContrastColor';
import extractDate from '../utils/extractDate';
import '../styles/MapPanel.css';

// ── 지구 거리 계산 (미터) ──
const haversineDistanceM = (c1, c2) => {
  const R = 6371000;
  const φ1 = c1.lat * Math.PI / 180, φ2 = c2.lat * Math.PI / 180;
  const Δφ = (c2.lat - c1.lat) * Math.PI / 180;
  const Δλ = (c2.lng - c1.lng) * Math.PI / 180;
  const a = Math.sin(Δφ/2)**2 + Math.cos(φ1)*Math.cos(φ2)*Math.sin(Δλ/2)**2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
};

// ── 연속 위치 클러스터링 (50m 이내 인접 그룹화) ──
const clusterAdjacentLocations = (locs, radiusM = 50) => {
  if (locs.length === 0) return [];
  const clusters = [];
  let group = [locs[0]];
  for (let i = 1; i < locs.length; i++) {
    const dist = haversineDistanceM(group[group.length - 1].coordinates, locs[i].coordinates);
    if (dist <= radiusM) {
      group.push(locs[i]);
    } else {
      clusters.push(group);
      group = [locs[i]];
    }
  }
  clusters.push(group);
  return clusters.map(group => ({
    ...group[0],
    coordinates: {
      lat: group.reduce((s, l) => s + l.coordinates.lat, 0) / group.length,
      lng: group.reduce((s, l) => s + l.coordinates.lng, 0) / group.length,
    },
    photoCount: group.length,
    allIds: group.map(l => l.id),
  }));
};

// ── GPS 시간/거리로 이동 수단 자동 추정 ──
const estimateTravelMode = (locs) => {
  if (locs.length < 2) return 'driving';
  const speeds = [];
  for (let i = 0; i < locs.length - 1; i++) {
    const a = locs[i], b = locs[i + 1];
    if (!a.captureTimestamp || !b.captureTimestamp) continue;
    const timeDiffH = Math.abs(b.captureTimestamp - a.captureTimestamp) / 3600000;
    if (timeDiffH < 0.001) continue;
    const distKm = haversineDistanceM(a.coordinates, b.coordinates) / 1000;
    speeds.push(distKm / timeDiffH);
  }
  if (speeds.length === 0) return 'driving';
  const avg = speeds.reduce((s, v) => s + v, 0) / speeds.length;
  if (avg < 6) return 'walking';
  if (avg < 25) return 'bicycling';
  return 'driving';
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
  showRoutes,
  directionsData,
  useDirections,
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
        mapTypeId: mapType,
        mapId: process.env.REACT_APP_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID',
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
    if (!map) return;

    // 기존 경로 선 항상 제거
    routeLines.forEach(line => line.setMap(null));

    if (locations.length < 2 || !showRoutes) {
      setRouteLines([]);
      return;
    }

    const newRouteLines = [];

    // Directions API 데이터가 있으면 인코딩된 폴리라인 사용
    if (useDirections && directionsData?.segments) {
      for (const segment of directionsData.segments) {
        if (segment.polyline) {
          try {
            const path = window.google.maps.geometry.encoding.decodePath(segment.polyline);
            const routeLine = new window.google.maps.Polyline({
              path,
              strokeColor: '#4285F4',
              strokeOpacity: 0.9,
              strokeWeight: 4,
              map: map,
            });
            newRouteLines.push(routeLine);
          } catch {
            // 디코딩 실패 시 직선 폴백
          }
        }
      }
    }

    // Directions 데이터가 없거나 비활성화면 직선 경로
    if (newRouteLines.length === 0) {
      for (let i = 0; i < locations.length - 1; i++) {
        const routeLine = new window.google.maps.Polyline({
          path: [locations[i].coordinates, locations[i + 1].coordinates],
          geodesic: true,
          strokeColor: locations[i].color || '#ff6b6b',
          strokeOpacity: 0.8,
          strokeWeight: 3,
          map: map,
        });
        newRouteLines.push(routeLine);
      }
    }

    setRouteLines(newRouteLines);
  }, [map, locations, showRoutes, useDirections, directionsData]);

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
  const { locations, selectedPhotoId, photos } = useSelector(state => state.photos);
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [mapType, setMapType] = useState('roadmap');
  const [center, setCenter] = useState({ lat: 37.566535, lng: 126.977969 });
  const [zoom, setZoom] = useState(12);
  const [showRoutes, setShowRoutes] = useState(true);
  const [isAddingLocation, setIsAddingLocation] = useState(false);
  const [editingLocationId, setEditingLocationId] = useState(null);
  const [editForm, setEditForm] = useState({ lat: '', lng: '' });
  const [useDirections, setUseDirections] = useState(false);
  const [directionsData, setDirectionsData] = useState(null);
  const [directionsLoading, setDirectionsLoading] = useState(false);
  const [travelMode, setTravelMode] = useState('driving');

  // 클러스터링된 표시용 위치 목록
  const displayLocations = clusterAdjacentLocations(locations);

  // 위치/타임스탬프 변경 시 이동 수단 자동 감지
  useEffect(() => {
    if (locations.length >= 2) {
      const detected = estimateTravelMode(locations);
      setTravelMode(detected);
    }
  }, [locations]);

  // Directions API 호출
  const fetchDirections = useCallback(async () => {
    if (displayLocations.length < 2) {
      setDirectionsData(null);
      return;
    }
    setDirectionsLoading(true);
    try {
      const waypoints = displayLocations.map(loc => ({
        lat: loc.coordinates.lat,
        lng: loc.coordinates.lng
      }));
      const res = await apiClient.post('/api/v1/routes/directions', {
        waypoints,
        mode: travelMode
      });
      if (res.data && !res.data.error) {
        setDirectionsData(res.data);
      } else {
        setDirectionsData(null);
      }
    } catch {
      setDirectionsData(null);
    } finally {
      setDirectionsLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locations, travelMode]);

  // useDirections 토글 시 또는 locations/travelMode 변경 시 경로 조회
  useEffect(() => {
    if (useDirections && locations.length >= 2) {
      fetchDirections();
    } else {
      setDirectionsData(null);
    }
  }, [useDirections, locations, travelMode, fetchDirections]);

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
    if (!isAddingLocation) return;

    // GPS가 없는 첫 번째 활성 사진에 위치 할당
    const photoWithoutGPS = photos.find(p => p.isActive && (!p.gpsData || !p.gpsData.lat));
    if (photoWithoutGPS) {
      dispatch(updatePhotoGPS({
        photoId: photoWithoutGPS.id,
        gpsData: { lat, lng }
      }));
    }
    setIsAddingLocation(false);
  }, [isAddingLocation, photos, dispatch]);

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
    const location = locations.find(loc => loc.id === locationId);
    if (location) {
      setEditingLocationId(locationId);
      setEditForm({
        lat: location.coordinates.lat.toString(),
        lng: location.coordinates.lng.toString()
      });
    }
  };

  const handleEditSave = () => {
    if (editingLocationId) {
      const lat = parseFloat(editForm.lat);
      const lng = parseFloat(editForm.lng);
      if (!isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
        dispatch(updatePhotoGPS({
          photoId: editingLocationId,
          gpsData: { lat, lng }
        }));
        setEditingLocationId(null);
        setEditForm({ lat: '', lng: '' });
      }
    }
  };

  const handleEditCancel = () => {
    setEditingLocationId(null);
    setEditForm({ lat: '', lng: '' });
  };

  const handleLocationDelete = (locationId) => {
    dispatch(togglePhotoActive(locationId));
  };

  const formatTimeDiff = (msA, msB) => {
    const diff = Math.abs(msB - msA);
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    if (hours > 0) return `${hours}시간 ${minutes}분`;
    if (minutes > 0) return `${minutes}분`;
    return '1분 미만';
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
          <button
            className={`map-control-btn route-toggle ${showRoutes ? 'active' : ''}`}
            onClick={() => setShowRoutes(!showRoutes)}
            title={showRoutes ? '경로 숨기기' : '경로 표시'}
          >
            ⟿
          </button>
          <button
            className={`map-control-btn route-toggle ${useDirections ? 'active' : ''}`}
            onClick={() => setUseDirections(!useDirections)}
            title={useDirections ? '직선 경로로 전환' : '실제 도로 경로로 전환'}
            disabled={directionsLoading}
          >
            {directionsLoading ? '…' : '🛣'}
          </button>
        </div>
      </div>

      <div className="map-container">
        <Wrapper apiKey={apiKey} libraries={['geometry']} render={MapLoadingComponent}>
          <GoogleMapComponent
            center={center}
            zoom={zoom}
            locations={displayLocations}
            selectedLocation={selectedLocation}
            onLocationSelect={handleLocationSelect}
            mapType={mapType}
            onMapClick={handleMapClick}
            showRoutes={showRoutes}
            directionsData={directionsData}
            useDirections={useDirections}
          />
        </Wrapper>
      </div>

      {/* 도로 경로 요약 (이동 수단 자동 감지, 드롭다운 없음) */}
      {useDirections && directionsData && (
        <div className="directions-settings">
          <div className="route-summary">
            <div className="route-summary-item">
              <span className="route-summary-label">총 거리</span>
              <span className="route-summary-value">{directionsData.total_distance_text}</span>
            </div>
            <div className="route-summary-item">
              <span className="route-summary-label">총 시간</span>
              <span className="route-summary-value">{directionsData.total_duration_text}</span>
            </div>
            <div className="route-summary-item">
              <span className="route-summary-label">수단</span>
              <span className="route-summary-value">
                {{ driving: '자동차', walking: '도보', bicycling: '자전거', transit: '대중교통' }[travelMode] || travelMode}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="location-details">
        <div className="location-details-header">
          <h4>경로 요약 ({displayLocations.length}개 지점)</h4>
          <button
            className={`add-location-btn ${isAddingLocation ? 'active' : ''}`}
            onClick={() => setIsAddingLocation(!isAddingLocation)}
            title="지도를 클릭하여 위치 추가"
          >
            {isAddingLocation ? '취소' : '+ 위치 추가'}
          </button>
        </div>
        {isAddingLocation && (
          <div className="add-location-hint">
            지도를 클릭하여 GPS 정보가 없는 사진에 위치를 지정하세요.
          </div>
        )}
        <div className="location-list">
          {displayLocations.map((location, index) => {
            const shouldShowDaySeparator = index > 0 && (() => {
              const currentDate = extractDate(location.time);
              const previousDate = extractDate(displayLocations[index - 1].time);
              return currentDate && previousDate && currentDate !== previousDate;
            })();

            const getDayNumber = (idx) => {
              const firstDate = extractDate(displayLocations[0].time);
              const currentDate = extractDate(displayLocations[idx].time);
              if (!firstDate || !currentDate) return 1;
              return Math.floor((new Date(currentDate) - new Date(firstDate)) / 86400000) + 1;
            };

            const isSelected = location.allIds
              ? location.allIds.some(id => selectedLocation === id)
              : selectedLocation === location.id;

            const elements = [];

            if (index === 0) {
              elements.push(
                <div key="day-1" className="day-separator">
                  <div className="day-separator-line" />
                  <span className="day-separator-text">1일차</span>
                  <div className="day-separator-line" />
                </div>
              );
            }

            if (shouldShowDaySeparator) {
              elements.push(
                <div key={`day-${getDayNumber(index)}`} className="day-separator">
                  <div className="day-separator-line" />
                  <span className="day-separator-text">{getDayNumber(index)}일차</span>
                  <div className="day-separator-line" />
                </div>
              );
            }

            if (index > 0 && displayLocations[index - 1].captureTimestamp && location.captureTimestamp) {
              const travelTime = formatTimeDiff(displayLocations[index - 1].captureTimestamp, location.captureTimestamp);
              elements.push(
                <div key={`travel-${location.id}`} className="travel-time-indicator">
                  <div className="travel-time-line" />
                  <span className="travel-time-label">↓ {travelTime} 후</span>
                  <div className="travel-time-line" />
                </div>
              );
            }

            elements.push(
              <div
                key={location.id}
                className={`location-item ${isSelected ? 'selected' : ''}`}
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
                    <span className="location-name">{location.name}</span>
                    {location.photoCount > 1 && (
                      <span className="cluster-count-badge">{location.photoCount}장</span>
                    )}
                  </div>
                  <div className="location-time">{location.time}</div>
                </div>
                {isSelected && editingLocationId !== location.id && (
                  <div className="location-actions">
                    <button
                      className="edit-location-btn"
                      onClick={(e) => { e.stopPropagation(); handleLocationEdit(location.id); }}
                    >
                      편집
                    </button>
                    <button
                      className="delete-location-btn"
                      onClick={(e) => { e.stopPropagation(); handleLocationDelete(location.id); }}
                    >
                      삭제
                    </button>
                  </div>
                )}
                {editingLocationId === location.id && (
                  <div className="location-edit-form" onClick={(e) => e.stopPropagation()}>
                    <div className="edit-field">
                      <label>위도</label>
                      <input type="number" step="0.000001" value={editForm.lat}
                        onChange={(e) => setEditForm({ ...editForm, lat: e.target.value })} />
                    </div>
                    <div className="edit-field">
                      <label>경도</label>
                      <input type="number" step="0.000001" value={editForm.lng}
                        onChange={(e) => setEditForm({ ...editForm, lng: e.target.value })} />
                    </div>
                    <div className="edit-actions">
                      <button className="save-btn" onClick={handleEditSave}>저장</button>
                      <button className="cancel-btn" onClick={handleEditCancel}>취소</button>
                    </div>
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