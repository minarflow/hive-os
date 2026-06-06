import { api } from './client'
import type { ChatMessage, ChatSession } from '../types'

export const listSessions = (token: string) => api<{ sessions: ChatSession[] }>('/api/sessions', token)
export const createSession = (token: string, body: { title?: string; project_slug?: string | null; profile_id?: number | null; visibility?: 'private' | 'project' }) => api<ChatSession>('/api/sessions', token, { method: 'POST', body: JSON.stringify(body) })
export const listMessages = (token: string, sessionId: number) => api<{ messages: ChatMessage[] }>(`/api/sessions/${sessionId}/messages`, token)
export const renameSession = (token: string, sessionId: number, title: string) => api<ChatSession>(`/api/sessions/${sessionId}`, token, { method: 'PATCH', body: JSON.stringify({ title }) })
export const deleteSession = (token: string, sessionId: number) => api<{ ok: boolean }>(`/api/sessions/${sessionId}`, token, { method: 'DELETE' })
