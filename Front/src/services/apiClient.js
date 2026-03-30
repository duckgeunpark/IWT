const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const handleResponse = async (response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(errorData.detail || `HTTP ${response.status}`);
    error.status = response.status;
    error.data = errorData;
    throw error;
  }
  return response.json();
};

export const apiClient = {
  get: async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });
    return handleResponse(response);
  },

  post: async (path, body, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: JSON.stringify(body),
      ...options,
    });
    return handleResponse(response);
  },

  put: async (path, body, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      body: JSON.stringify(body),
      ...options,
    });
    return handleResponse(response);
  },

  delete: async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });
    return handleResponse(response);
  },
};

export default apiClient;
