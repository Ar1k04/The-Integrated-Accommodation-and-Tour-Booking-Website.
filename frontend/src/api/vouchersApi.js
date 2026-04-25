import api from './axiosInstance'

export const vouchersApi = {
  validate: (code, subtotal) =>
    api.post('/vouchers/validate', { code, subtotal }),
  list: (params) => api.get('/vouchers', { params }),
  create: (data) => api.post('/vouchers', data),
  update: (id, data) => api.patch(`/vouchers/${id}`, data),
  delete: (id) => api.delete(`/vouchers/${id}`),
}
