import { configureStore } from '@reduxjs/toolkit';
import photoReducer from './photoSlice';

export const store = configureStore({
  reducer: {
    photos: photoReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // File 객체는 serializable하지 않으므로 무시
        ignoredActions: ['photos/addPhoto', 'photos/updatePhotoGPS'],
        ignoredPaths: ['photos.photos.file'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;