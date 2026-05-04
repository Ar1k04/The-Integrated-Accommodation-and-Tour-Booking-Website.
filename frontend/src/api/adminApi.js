import api from './axiosInstance'

export const adminApi = {
  getStats: (params) => api.get('/admin/stats', { params }),
  listUsers: (params) => api.get('/admin/users', { params }),
  getUser: (id) => api.get(`/admin/users/${id}`),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
  listBookings: (params) => api.get('/admin/bookings', { params }),
  updateBooking: (id, status) => api.patch(`/admin/bookings/${id}?status=${status}`),
  listWishlists: (params) => api.get('/wishlists', { params }),
  addToWishlist: (data) => api.post('/wishlists', data),
  removeFromWishlist: (id) => api.delete(`/wishlists/${id}`),
}
