import axios from 'axios';
import { TOKEN_KEY, clearStoredAuth, isTokenExpired } from '../utils/authToken';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    if (isTokenExpired(token)) {
      clearStoredAuth();
      return config;
    }
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const requestUrl = error.config?.url || '';
    const isLoginRequest =
      requestUrl.includes('/auth/login') ||
      requestUrl.includes('/auth/register') ||
      requestUrl.includes('/faculty/login');

    if (status === 401 && !isLoginRequest) {
      clearStoredAuth();
      const nextLoginPath = window.location.pathname.startsWith('/faculty') ? '/faculty/login' : '/login';
      if (window.location.pathname !== nextLoginPath) {
        window.location.href = nextLoginPath;
      }
    }
    return Promise.reject(error);
  }
);

export default api;

