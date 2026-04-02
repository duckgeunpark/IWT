import { configureStore } from '@reduxjs/toolkit';
import photoReducer from './photoSlice';

export const store = configureStore({
  reducer: {
    photos: photoReducer,
  },
});
