import { request } from './client'

export const get_behaviors = (options = {}) => request('/api/behaviors', options)
