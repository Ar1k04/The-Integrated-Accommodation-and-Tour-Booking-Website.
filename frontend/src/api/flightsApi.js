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

  // Order changes (3-step user wizard)
  createChangeRequest: (duffelOrderId, body) =>
    api.post(`/flights/orders/${duffelOrderId}/change-requests`, body),
  getChangeRequest: (ocrId) => api.get(`/flights/change-requests/${ocrId}`),
  listChangeOffers: (ocrId, params) =>
    api.get(`/flights/change-requests/${ocrId}/offers`, { params }),
  getChangeOffer: (ocoId) => api.get(`/flights/change-offers/${ocoId}`),
  selectChangeOffer: (ocoId) =>
    api.post(`/flights/change-offers/${ocoId}/select`),
  getOrderChange: (ocId) => api.get(`/flights/order-changes/${ocId}`),
  createChangePaymentIntent: (ocId) =>
    api.post(`/flights/order-changes/${ocId}/payment-intent`),
  confirmOrderChange: (ocId, body) =>
    api.post(`/flights/order-changes/${ocId}/confirm`, body),
}
