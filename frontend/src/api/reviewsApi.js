import api from './axiosInstance'

export const reviewsApi = {
  listHotelReviews: (hotelId, params) => api.get(`/hotels/${hotelId}/reviews`, { params }),
  listTourReviews: (tourId, params) => api.get(`/tours/${tourId}/reviews`, { params }),
  listViatorTourReviews: (code, params) => api.get(`/tours/viator/${code}/reviews`, { params }),
  create: (data) => api.post('/reviews', data),
  update: (id, data) => api.patch(`/reviews/${id}`, data),
  delete: (id) => api.delete(`/reviews/${id}`),
}
