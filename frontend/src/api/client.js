import axios from 'axios';

function serializeParams(params = {}) {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    if (Array.isArray(value)) {
      value.forEach(item => {
        if (item !== undefined && item !== null && item !== '') {
          searchParams.append(key, item);
        }
      });
      return;
    }
    searchParams.append(key, value);
  });
  return searchParams.toString();
}

const apiClient = axios.create ? axios.create({ paramsSerializer: serializeParams }) : axios;

let unauthorizedHandler = null;

apiClient.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401 && !error.config?.url?.includes('/api/auth/login')) {
      unauthorizedHandler?.(error);
    }
    return Promise.reject(error);
  }
);

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) {
      unauthorizedHandler = null;
    }
  };
}

export default apiClient;
