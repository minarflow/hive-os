import { api } from './client'
import type { Project } from '../types'

export type Member = { username: string; os_user: string; role: string }
export const listProjects = (token: string) => api<{ projects: Project[] }>('/api/projects', token)
export const createProject = (token: string, body: { slug: string; name: string; visibility: 'private' | 'shared' }) => api<Project>('/api/projects', token, { method: 'POST', body: JSON.stringify(body) })
export const listMembers = (token: string, slug: string) => api<{ members: Member[] }>(`/api/projects/${slug}/members`, token)
export const inviteMember = (token: string, slug: string, username: string) => api<{ ok: boolean }>(`/api/projects/${slug}/invite`, token, { method: 'POST', body: JSON.stringify({ username }) })
export const removeMember = (token: string, slug: string, username: string) => api<{ ok: boolean }>(`/api/projects/${slug}/remove`, token, { method: 'POST', body: JSON.stringify({ username }) })
export const deleteProject = (token: string, slug: string) => api<{ ok: boolean }>(`/api/projects/${slug}`, token, { method: 'DELETE' })
