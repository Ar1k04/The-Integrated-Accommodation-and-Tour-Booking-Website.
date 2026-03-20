import api from './axiosInstance'

export const adminApi = {
  getStats: (params) => api.get('/admin/stats', { params }),
  listUsers: (params) => api.get('/admin/users', { params }),
  getUser: (id) => api.get(`/admin/users/${id}`),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
  listBookings: (params) => api.get('/admin/bookings', { params }),
  updateBooking: (id, status) => api.patch(`/admin/bookings/${id}?status=${status}`),

  listPromoCodes: (params) => api.get('/promo-codes', { params }),
  createPromoCode: (data) => api.post('/promo-codes', data),
  updatePromoCode: (id, data) => api.patch(`/promo-codes/${id}`, data),
  deletePromoCode: (id) => api.delete(`/promo-codes/${id}`),
  validatePromoCode: (params) => api.post('/promo-codes/validate', null, { params }),

  listWishlists: (params) => api.get('/wishlists', { params }),
  addToWishlist: (data) => api.post('/wishlists', data),
  removeFromWishlist: (id) => api.delete(`/wishlists/${id}`),
}
