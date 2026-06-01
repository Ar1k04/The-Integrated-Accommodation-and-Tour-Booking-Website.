import api from './axiosInstance'

export const vouchersApi = {
  validate: (code, subtotal) =>
    api.post('/vouchers/validate', { code, subtotal }),
  available: () => api.get('/vouchers/available'),
  list: (params) => api.get('/vouchers', { params }),
  create: (data) => api.post('/vouchers', data),
  update: (id, data) => api.patch(`/vouchers/${id}`, data),
  delete: (id) => api.delete(`/vouchers/${id}`),
  toggleStatus: (id, status) => api.patch(`/vouchers/${id}/status`, { status }),
  listUsages: (voucherId, params) =>
    api.get(`/vouchers/${voucherId}/usages`, { params }),
  listAllUsages: (params) => api.get('/vouchers/usages', { params }),
  syncToLiteapi: (id) => api.post(`/vouchers/${id}/sync-liteapi`),
  unsyncFromLiteapi: (id) => api.delete(`/vouchers/${id}/sync-liteapi`),
}
