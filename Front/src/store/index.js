import { configureStore } from '@reduxjs/toolkit';
import photoReducer from './photoSlice';
import socialReducer from './socialSlice';
import notificationReducer from './notificationSlice';

export const store = configureStore({
  reducer: {
    photos: photoReducer,
    social: socialReducer,
    notifications: notificationReducer,
  },
});
