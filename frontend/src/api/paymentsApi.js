import api from './axiosInstance'

export const paymentsApi = {
  create: (data) => api.post('/payments', data),
  get: (id) => api.get(`/payments/${id}`),
  refund: (id) => api.delete(`/payments/${id}`),

  createVnpayUrl: (data) => api.post('/payments/vnpay/create', data),
  verifyVnpayReturn: (params) =>
    api.get('/payments/vnpay/return', { params }),
}
