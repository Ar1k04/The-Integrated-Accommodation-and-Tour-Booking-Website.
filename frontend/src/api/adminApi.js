import api from './axiosInstance'

export const adminApi = {
  getStats: (params) => api.get('/admin/stats', { params }),
  listUsers: (params) => api.get('/admin/users', { params }),
  getUser: (id) => api.get(`/admin/users/${id}`),
  updateUser: (id, data) => api.patch(`/admin/users/${id}`, data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`),
  listBookings: (params) => api.get('/admin/bookings', { params }),
  updateBooking: (id, status) => api.patch(`/admin/bookings/${id}?status=${status}`),
  syncLiteapiBooking: (id) => api.post(`/admin/bookings/${id}/sync-liteapi`),
  listWishlists: (params) => api.get('/wishlists', { params }),
  addToWishlist: (data) => api.post('/wishlists', data),
  removeFromWishlist: (id) => api.delete(`/wishlists/${id}`),
  // Partner approval (UC_A_PARTNERS)
  listPartners: (params) => api.get('/admin/partners', { params }),
  updatePartnerStatus: (id, partner_status) => api.patch(`/admin/partners/${id}`, { partner_status }),
  // Loyalty tiers (UC_A_TIERS)
  listTiers: () => api.get('/admin/loyalty-tiers'),
  createTier: (data) => api.post('/admin/loyalty-tiers', data),
  updateTier: (id, data) => api.patch(`/admin/loyalty-tiers/${id}`, data),
  deleteTier: (id) => api.delete(`/admin/loyalty-tiers/${id}`),
  recomputeTiers: () => api.post('/admin/loyalty-tiers/recompute'),
}
