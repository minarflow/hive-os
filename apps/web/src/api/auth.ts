import { api } from './client'
import type { Profile, User } from '../types'

export type SetupStatus = { bootstrap_required: boolean; mode: string; hermes_profiles_root: string; runners?: { id: string; displayName: string; installed: boolean }[] }
export const getSetupStatus = () => api<SetupStatus>('/api/setup/status')
export const bootstrap = (body: { username: string; password: string; profile_name: string; profile_slug: string; runner_id?: string }) =>
  api<{ token: string; user: User; profile: Profile }>('/api/setup/bootstrap', undefined, { method: 'POST', body: JSON.stringify(body) })
export const login = (username: string, password: string) => api<{ token: string; user: User }>('/auth/login', undefined, { method: 'POST', body: JSON.stringify({ username, password }) })
export const me = (token: string) => api<User>('/api/me', token)
export const logout = (token: string) => api<{ ok: boolean }>('/auth/logout', token, { method: 'POST' })
export const changePassword = (token: string, current_password: string, new_password: string) =>
  api<{ ok: boolean; message: string }>('/api/me/password', token, { method: 'POST', body: JSON.stringify({ current_password, new_password }) })
