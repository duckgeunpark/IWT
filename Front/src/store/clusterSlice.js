import { createSlice } from '@reduxjs/toolkit';

const haversineDistance = (lat1, lng1, lat2, lng2) => {
  const R = 6371;
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const dphi = ((lat2 - lat1) * Math.PI) / 180;
  const dlambda = ((lng2 - lng1) * Math.PI) / 180;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dlambda / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
};

const clusterSlice = createSlice({
  name: 'clusters',
  initialState: {
    clusters: [],
  },
  reducers: {
    setClusters(state, action) {
      // action.payload: [{cluster_id, photo_ids, location_name, section_heading}]
      state.clusters = action.payload.map(c => ({
        ...c,
        representative_photo_id: c.photo_ids?.[0] ?? null,
      }));
    },

    setRepresentativePhoto(state, action) {
      const { cluster_id, photo_id } = action.payload;
      const cluster = state.clusters.find(c => c.cluster_id === cluster_id);
      if (cluster) cluster.representative_photo_id = photo_id;
    },

    addPhotoToCluster(state, action) {
      const { cluster_id, photo_id } = action.payload;
      const cluster = state.clusters.find(c => c.cluster_id === cluster_id);
      if (cluster && !cluster.photo_ids.includes(photo_id)) {
        cluster.photo_ids.push(photo_id);
      }
    },

    // ImagePanel에서 사진 추가 시 GPS/시간 기준으로 가장 가까운 클러스터에 자동 배정
    autoAssignToCluster(state, action) {
      const { photo_id, gps, taken_at } = action.payload;
      if (!state.clusters.length) return;

      let bestCluster = null;
      let bestScore = Infinity;

      for (const cluster of state.clusters) {
        let score = Infinity;

        // GPS 기반 거리 점수
        if (gps && cluster.center_gps) {
          score = haversineDistance(gps.lat, gps.lng, cluster.center_gps.lat, cluster.center_gps.lng);
        }

        // GPS 없으면 시간 기반 점수 (시간 차이 시간 단위)
        if (score === Infinity && taken_at && cluster.start_time) {
          const diff = Math.abs(new Date(taken_at) - new Date(cluster.start_time)) / 3600000;
          score = diff;
        }

        if (score < bestScore) {
          bestScore = score;
          bestCluster = cluster;
        }
      }

      if (bestCluster && !bestCluster.photo_ids.includes(photo_id)) {
        bestCluster.photo_ids.push(photo_id);
      }
    },

    clearClusters(state) {
      state.clusters = [];
    },
  },
});

export const {
  setClusters,
  setRepresentativePhoto,
  addPhotoToCluster,
  autoAssignToCluster,
  clearClusters,
} = clusterSlice.actions;

export default clusterSlice.reducer;
