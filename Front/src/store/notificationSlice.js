import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiClient } from '../services/apiClient';

export const fetchNotifications = createAsyncThunk(
  'notifications/fetchNotifications',
  async ({ limit = 50, offset = 0 } = {}) => {
    const res = await apiClient.get(`/api/v1/notifications?limit=${limit}&offset=${offset}`);
    return res.data;
  }
);

export const fetchUnreadCount = createAsyncThunk(
  'notifications/fetchUnreadCount',
  async () => {
    const res = await apiClient.get('/api/v1/notifications/unread-count');
    return res.data.unread_count;
  }
);

export const markAsRead = createAsyncThunk(
  'notifications/markAsRead',
  async (notificationId) => {
    await apiClient.put(`/api/v1/notifications/${notificationId}/read`);
    return notificationId;
  }
);

export const markAllAsRead = createAsyncThunk(
  'notifications/markAllAsRead',
  async () => {
    await apiClient.put('/api/v1/notifications/read-all');
  }
);

export const deleteNotification = createAsyncThunk(
  'notifications/deleteNotification',
  async (notificationId) => {
    await apiClient.delete(`/api/v1/notifications/${notificationId}`);
    return notificationId;
  }
);

const notificationSlice = createSlice({
  name: 'notifications',
  initialState: {
    items: [],
    unreadCount: 0,
    loading: false,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchNotifications.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchNotifications.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload.notifications;
        state.unreadCount = action.payload.unread_count;
      })
      .addCase(fetchNotifications.rejected, (state) => {
        state.loading = false;
      })
      .addCase(fetchUnreadCount.fulfilled, (state, action) => {
        state.unreadCount = action.payload;
      })
      .addCase(markAsRead.fulfilled, (state, action) => {
        const notif = state.items.find(n => n.id === action.payload);
        if (notif && !notif.is_read) {
          notif.is_read = true;
          state.unreadCount = Math.max(0, state.unreadCount - 1);
        }
      })
      .addCase(markAllAsRead.fulfilled, (state) => {
        state.items.forEach(n => { n.is_read = true; });
        state.unreadCount = 0;
      })
      .addCase(deleteNotification.fulfilled, (state, action) => {
        const idx = state.items.findIndex(n => n.id === action.payload);
        if (idx !== -1) {
          if (!state.items[idx].is_read) {
            state.unreadCount = Math.max(0, state.unreadCount - 1);
          }
          state.items.splice(idx, 1);
        }
      });
  },
});

export default notificationSlice.reducer;
