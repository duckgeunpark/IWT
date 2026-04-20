import { configureStore } from '@reduxjs/toolkit';
import photoReducer from './photoSlice';
import socialReducer from './socialSlice';
import notificationReducer from './notificationSlice';
import clusterReducer from './clusterSlice';

export const store = configureStore({
  reducer: {
    photos: photoReducer,
    social: socialReducer,
    notifications: notificationReducer,
    clusters: clusterReducer,
  },
});
