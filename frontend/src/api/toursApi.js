import api from './axiosInstance'

export const toursApi = {
  list: (params) => api.get('/tours', { params }),
  get: (id) => api.get(`/tours/${id}`),
  getAvailability: (id, params) => api.get(`/tours/${id}/availability`, { params }),
  getViator: (code) => api.get(`/tours/viator/${code}`),
  getViatorAvailability: (code, params) => api.get(`/tours/viator/${code}/availability`, { params }),
  getViatorTags: () => api.get('/tours/viator/tags'),
  searchViatorDestinations: (q, limit = 10) =>
    api.get('/tours/viator/destinations', { params: { q, limit } }),
  create: (data) => api.post('/tours', data),
  update: (id, data) => api.patch(`/tours/${id}`, data),
  delete: (id) => api.delete(`/tours/${id}`),
  uploadImages: (id, formData) =>
    api.post(`/tours/${id}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}
