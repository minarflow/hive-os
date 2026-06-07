import { api } from './client'

export type TeamUser = { id: number; username: string; os_user: string; role: string; created_at: string }

export const listUsers = (token: string) => api<{ users: TeamUser[] }>('/api/users', token)
export const updateUser = (token: string, id: number, body: { role?: string; password?: string }) =>
  api<{ user: TeamUser }>(`/api/users/${id}`, token, { method: 'PATCH', body: JSON.stringify(body) })
export const deleteUser = (token: string, id: number) =>
  api<{ ok: boolean }>(`/api/users/${id}`, token, { method: 'DELETE' })
