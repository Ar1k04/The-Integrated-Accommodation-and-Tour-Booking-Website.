import api from './axiosInstance'

export const roomsApi = {
  listByHotel: (hotelId, params) => api.get(`/hotels/${hotelId}/rooms`, { params }),
  get: (id) => api.get(`/rooms/${id}`),
  create: (hotelId, data) => api.post(`/hotels/${hotelId}/rooms`, data),
  update: (id, data) => api.patch(`/rooms/${id}`, data),
  delete: (id) => api.delete(`/rooms/${id}`),
  checkAvailability: (id, params) => api.get(`/rooms/${id}/availability`, { params }),
}
