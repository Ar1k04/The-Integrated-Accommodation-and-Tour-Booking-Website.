import api from './axiosInstance'

export const loyaltyApi = {
  getStatus: () => api.get('/loyalty/me'),
  redeem: (points, bookingId) =>
    api.post('/loyalty/redeem', { points, booking_id: bookingId ?? undefined }),
}
