import api from './axiosInstance'

export const featuredApi = {
  // Top-rated hotels (partner + LiteAPI) + tours (Viator) for the landing page.
  // `rateDate` is the viewer's local "today" (YYYY-MM-DD) — the backend runs UTC,
  // but a check-in date is a calendar date in the user's own zone, so we send it.
  // The external feed is cached permanently on the backend; rates are cached per day.
  home: (rateDate) =>
    api.get('/featured/home', { params: rateDate ? { rate_date: rateDate } : undefined }),
}
