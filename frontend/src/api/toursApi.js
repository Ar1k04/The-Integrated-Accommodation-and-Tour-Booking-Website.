import api from './axiosInstance'

export const toursApi = {
  list: (params) => api.get('/tours', { params }),
  get: (id) => api.get(`/tours/${id}`),
  getViator: (code) => api.get(`/tours/viator/${code}`),
  getViatorAvailability: (code, params) => api.get(`/tours/viator/${code}/availability`, { params }),
  getViatorTags: () => api.get('/tours/viator/tags'),
  searchViatorDestinations: (q, limit = 10) =>
    api.get('/tours/viator/destinations', { params: { q, limit } }),
  create: (data) => api.post('/tours', data),
  update: (id, data) => api.patch(`/tours/${id}`, data),
  delete: (id) => api.delete(`/tours/${id}`),

}
