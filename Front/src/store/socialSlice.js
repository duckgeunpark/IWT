import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiClient } from '../services/apiClient';

// ── Async Thunks ──

export const fetchPostSocialInfo = createAsyncThunk(
  'social/fetchPostSocialInfo',
  async (postId, { rejectWithValue }) => {
    try {
      const data = await apiClient.get(`/api/v1/posts/${postId}/social`);
      return { postId, ...data };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const toggleLike = createAsyncThunk(
  'social/toggleLike',
  async (postId, { rejectWithValue }) => {
    try {
      const data = await apiClient.post(`/api/v1/posts/${postId}/like`);
      return { postId, ...data };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const toggleBookmark = createAsyncThunk(
  'social/toggleBookmark',
  async (postId, { rejectWithValue }) => {
    try {
      const data = await apiClient.post(`/api/v1/posts/${postId}/bookmark`);
      return { postId, ...data };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchComments = createAsyncThunk(
  'social/fetchComments',
  async ({ postId, skip = 0, limit = 20 }, { rejectWithValue }) => {
    try {
      const data = await apiClient.get(`/api/v1/posts/${postId}/comments?skip=${skip}&limit=${limit}`);
      return { postId, ...data };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const createComment = createAsyncThunk(
  'social/createComment',
  async ({ postId, content, parentId }, { rejectWithValue }) => {
    try {
      const body = { content };
      if (parentId) body.parent_id = parentId;
      const data = await apiClient.post(`/api/v1/posts/${postId}/comments`, body);
      return { postId, comment: data };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const deleteComment = createAsyncThunk(
  'social/deleteComment',
  async ({ postId, commentId }, { rejectWithValue }) => {
    try {
      await apiClient.delete(`/api/v1/comments/${commentId}`);
      return { postId, commentId };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const toggleFollow = createAsyncThunk(
  'social/toggleFollow',
  async (userId, { rejectWithValue }) => {
    try {
      const data = await apiClient.post(`/api/v1/users/${userId}/follow`);
      return { userId, ...data };
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

export const fetchFeed = createAsyncThunk(
  'social/fetchFeed',
  async ({ skip = 0, limit = 10 }, { rejectWithValue }) => {
    try {
      const data = await apiClient.get(`/api/v1/feed?skip=${skip}&limit=${limit}`);
      return data;
    } catch (err) {
      return rejectWithValue(err.message);
    }
  }
);

// ── Slice ──

const socialSlice = createSlice({
  name: 'social',
  initialState: {
    postSocial: {},
    postComments: {},
    followStatus: {},
    feed: { posts: [], total: 0 },
    isLoading: false,
    error: null,
  },
  reducers: {
    clearSocialError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPostSocialInfo.fulfilled, (state, action) => {
        const { postId, ...info } = action.payload;
        state.postSocial[postId] = info;
      })
      .addCase(toggleLike.fulfilled, (state, action) => {
        const { postId, liked, likes_count } = action.payload;
        if (!state.postSocial[postId]) state.postSocial[postId] = {};
        state.postSocial[postId].is_liked = liked;
        state.postSocial[postId].likes_count = likes_count;
      })
      .addCase(toggleBookmark.fulfilled, (state, action) => {
        const { postId, bookmarked, bookmarks_count } = action.payload;
        if (!state.postSocial[postId]) state.postSocial[postId] = {};
        state.postSocial[postId].is_bookmarked = bookmarked;
        state.postSocial[postId].bookmarks_count = bookmarks_count;
      })
      .addCase(fetchComments.fulfilled, (state, action) => {
        const { postId, comments, total } = action.payload;
        state.postComments[postId] = { comments, total };
      })
      .addCase(createComment.fulfilled, (state, action) => {
        const { postId, comment } = action.payload;
        if (!state.postComments[postId]) {
          state.postComments[postId] = { comments: [], total: 0 };
        }
        state.postComments[postId].comments.unshift(comment);
        state.postComments[postId].total += 1;
        if (state.postSocial[postId]) {
          state.postSocial[postId].comments_count = (state.postSocial[postId].comments_count || 0) + 1;
        }
      })
      .addCase(deleteComment.fulfilled, (state, action) => {
        const { postId, commentId } = action.payload;
        if (state.postComments[postId]) {
          state.postComments[postId].comments = state.postComments[postId].comments.filter(
            (c) => c.id !== commentId
          );
          state.postComments[postId].total -= 1;
        }
        if (state.postSocial[postId]) {
          state.postSocial[postId].comments_count = Math.max(
            0,
            (state.postSocial[postId].comments_count || 1) - 1
          );
        }
      })
      .addCase(toggleFollow.fulfilled, (state, action) => {
        const { userId, ...info } = action.payload;
        state.followStatus[userId] = info;
      })
      .addCase(fetchFeed.fulfilled, (state, action) => {
        state.feed = action.payload;
      })
      .addMatcher(
        (action) => action.type.startsWith('social/') && action.type.endsWith('/rejected'),
        (state, action) => {
          state.isLoading = false;
          state.error = action.payload || action.error?.message;
        }
      )
      .addMatcher(
        (action) => action.type.startsWith('social/') && action.type.endsWith('/pending'),
        (state) => {
          state.isLoading = true;
          state.error = null;
        }
      )
      .addMatcher(
        (action) => action.type.startsWith('social/') && action.type.endsWith('/fulfilled'),
        (state) => {
          state.isLoading = false;
        }
      );
  },
});

export const { clearSocialError } = socialSlice.actions;
export default socialSlice.reducer;
