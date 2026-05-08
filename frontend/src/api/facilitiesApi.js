import api from './axiosInstance'

export const facilitiesApi = {
  list: () => api.get('/hotels/facilities'),
}
