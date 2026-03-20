import api from './axiosInstance'

export const hotelsApi = {
  list: (params) => api.get('/hotels', { params }),
  get: (id) => api.get(`/hotels/${id}`),
  create: (data) => api.post('/hotels', data),
  update: (id, data) => api.patch(`/hotels/${id}`, data),
  replace: (id, data) => api.put(`/hotels/${id}`, data),
  delete: (id) => api.delete(`/hotels/${id}`),
  uploadImages: (id, formData) =>
    api.post(`/hotels/${id}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}
