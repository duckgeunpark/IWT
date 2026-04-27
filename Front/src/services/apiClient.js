const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

let _getAccessToken = null;

/**
 * Auth0 토큰 획득 함수를 등록한다.
 * App.js에서 Auth0Provider 내부에서 호출해야 한다.
 */
export const setTokenProvider = (getAccessTokenSilently) => {
  _getAccessToken = getAccessTokenSilently;
};

const getAuthHeaders = async () => {
  if (!_getAccessToken) return {};
  try {
    const token = await _getAccessToken();
    return { Authorization: `Bearer ${token}` };
  } catch {
    return {};
  }
};

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const handleResponse = async (response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(errorData.detail || `HTTP ${response.status}`);
    error.status = response.status;
    error.errorCode = errorData.error_code || null;
    error.data = errorData;
    throw error;
  }

  const text = await response.text();
  if (!text) return null;
  return JSON.parse(text);
};

/**
 * 재시도 로직이 포함된 fetch wrapper
 * 네트워크 에러 또는 5xx 응답 시 최대 retries회 재시도
 */
const fetchWithRetry = async (url, options, retries = 2) => {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, options);

      // 5xx 에러이고 재시도 가능하면 재시도
      if (response.status >= 500 && attempt < retries) {
        await wait(1000 * (attempt + 1));
        continue;
      }

      return response;
    } catch (error) {
      // 네트워크 에러 시 재시도
      if (attempt < retries) {
        await wait(1000 * (attempt + 1));
        continue;
      }
      throw error;
    }
  }
};

const request = async (method, path, body, options = {}) => {
  const authHeaders = await getAuthHeaders();
  const isFormData = body instanceof FormData;

  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...authHeaders,
    ...options.headers,
  };

  const fetchOptions = {
    method,
    headers,
    ...options,
  };

  if (body && method !== 'GET') {
    fetchOptions.body = isFormData ? body : JSON.stringify(body);
  }

  const response = await fetchWithRetry(
    `${API_BASE}${path}`,
    fetchOptions,
    options.retries ?? 2
  );

  return handleResponse(response);
};

/**
 * SSE(Server-Sent Events) 스트리밍용 POST — 파싱하지 않고 raw Response 반환
 */
const postStreamRaw = async (path, body, options = {}) => {
  const authHeaders = await getAuthHeaders();
  const headers = {
    'Content-Type': 'application/json',
    ...authHeaders,
    ...options.headers,
  };
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const error = new Error(errorData.detail || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return response;
};

export const apiClient = {
  get: (path, options = {}) => request('GET', path, null, options),
  post: (path, body, options = {}) => request('POST', path, body, options),
  put: (path, body, options = {}) => request('PUT', path, body, options),
  patch: (path, body, options = {}) => request('PATCH', path, body, options),
  delete: (path, options = {}) => request('DELETE', path, null, options),
  postStream: postStreamRaw,
};

export default apiClient;
