import { api } from './client'
import type { Profile } from '../types'

export const listProfiles = (token: string) => api<{ profiles: Profile[] }>('/api/profiles', token)
export const createProfile = (token: string, body: { slug: string; name: string; default_model?: string; runner_id?: string }) => api<Profile>('/api/profiles', token, { method: 'POST', body: JSON.stringify(body) })
export const updateProfile = (token: string, id: number, body: Partial<{ name: string; default_model: string; is_default: boolean; runner_id: string }>) => api<Profile>(`/api/profiles/${id}`, token, { method: 'PATCH', body: JSON.stringify(body) })
export const deleteProfile = (token: string, id: number) => api<{ ok: boolean }>(`/api/profiles/${id}`, token, { method: 'DELETE' })
