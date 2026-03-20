import api from './axiosInstance'

export const toursApi = {
  list: (params) => api.get('/tours', { params }),
  get: (id) => api.get(`/tours/${id}`),
  create: (data) => api.post('/tours', data),
  update: (id, data) => api.patch(`/tours/${id}`, data),
  delete: (id) => api.delete(`/tours/${id}`),

  listBookings: (params) => api.get('/tour-bookings', { params }),
  getBooking: (id) => api.get(`/tour-bookings/${id}`),
  createBooking: (data) => api.post('/tour-bookings', data),
  updateBooking: (id, data) => api.patch(`/tour-bookings/${id}`, data),
  cancelBooking: (id) => api.delete(`/tour-bookings/${id}`),
}
