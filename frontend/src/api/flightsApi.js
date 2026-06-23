import api from './axiosInstance'

export const flightsApi = {
  // v1 search
  search: (params) => api.get('/flights/search', { params }),

  searchAirports: (q, limit = 10) =>
    api.get('/flights/airports', { params: { q, limit } }),

  // Offers
  getOffer: (duffelOfferId) => api.get(`/flights/offers/${duffelOfferId}`),
  getSeatMaps: (duffelOfferId) => api.get(`/flights/seat-maps/${duffelOfferId}`),
  getAvailableServices: (duffelOfferId) =>
    api.get(`/flights/offers/${duffelOfferId}/available_services`),

  // Orders
  getOrder: (duffelOrderId) => api.get(`/flights/orders/${duffelOrderId}`),
  syncOrder: (duffelOrderId) => api.post(`/flights/orders/${duffelOrderId}/sync`),
  retryDuffelOrder: (bookingItemId) =>
    api.post(`/flights/bookings/${bookingItemId}/retry-duffel-order`),
}
