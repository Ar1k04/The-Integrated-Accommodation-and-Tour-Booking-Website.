import api from './axiosInstance'

export const paymentsApi = {
  create: (data) => api.post('/payments', data),
  get: (id) => api.get(`/payments/${id}`),
  refund: (id) => api.delete(`/payments/${id}`),
}
