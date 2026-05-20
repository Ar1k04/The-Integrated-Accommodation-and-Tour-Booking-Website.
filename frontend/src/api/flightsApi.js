import api from './axiosInstance'

export const flightsApi = {
  search: (params) => api.get('/flights/search', { params }),
  getOffer: (duffelOfferId) => api.get(`/flights/offers/${duffelOfferId}`),
  searchAirports: (q, limit = 10) =>
    api.get('/flights/airports', { params: { q, limit } }),
  getOrder: (duffelOrderId) => api.get(`/flights/orders/${duffelOrderId}`),
  syncOrder: (duffelOrderId) =>
    api.post(`/flights/orders/${duffelOrderId}/sync`),
  getSeatMaps: (duffelOfferId) =>
    api.get(`/flights/seat-maps/${duffelOfferId}`),
  getAvailableServices: (duffelOfferId) =>
    api.get(`/flights/offers/${duffelOfferId}/available_services`),
}
