import api from './axiosInstance'

export const authApi = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  refreshToken: () => api.post('/auth/token/refresh', null, { _retry: true }),
  forgotPassword: (email) => api.post('/auth/password/forgot', { email }),
  resetPassword: (data) => api.post('/auth/password/reset', data),
  getMe: (token) =>
    api.get('/auth/me', token ? { headers: { Authorization: `Bearer ${token}` } } : {}),
  updateMe: (data) => api.patch('/auth/me', data),
  changePassword: (data) => api.post('/auth/password/change', data),
}
