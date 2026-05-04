import api from './axiosInstance'

export const toursApi = {
  list: (params) => api.get('/tours', { params }),
  get: (id) => api.get(`/tours/${id}`),
  getViator: (code) => api.get(`/tours/viator/${code}`),
  getViatorAvailability: (code, params) => api.get(`/tours/viator/${code}/availability`, { params }),
  create: (data) => api.post('/tours', data),
  update: (id, data) => api.patch(`/tours/${id}`, data),
  delete: (id) => api.delete(`/tours/${id}`),

}
