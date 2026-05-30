import api from './axiosInstance'

export const hotelsApi = {
  list: (params) => api.get('/hotels', { params }),
  // Fast direct rates fetch for visible hotels — bypasses the BG :mid wait.
  minRates: (params) => api.get('/hotels/min-rates', { params }),
  get: (id) => api.get(`/hotels/${id}`),
  getLiteapi: (liteapiId) => api.get(`/hotels/liteapi/${liteapiId}`),
  getRates: (liteapiId, params) => api.get(`/hotels/liteapi/${liteapiId}/rates`, { params }),
  getLiteapiRoomTypes: (liteapiId) => api.get(`/hotels/liteapi/${liteapiId}/room-types`),
  getLiteapiReviews: (liteapiId, params) =>
    api.get(`/hotels/liteapi/${liteapiId}/reviews`, { params }),
  create: (data) => api.post('/hotels', data),
  update: (id, data) => api.patch(`/hotels/${id}`, data),
  replace: (id, data) => api.put(`/hotels/${id}`, data),
  delete: (id) => api.delete(`/hotels/${id}`),
  uploadImages: (id, formData) =>
    api.post(`/hotels/${id}/images`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}
