import { api } from './client'
import type { RunEvent } from '../types'

export const createRun = (token: string, sessionId: number, body: { message: string; profile_id?: number | null; model?: string | null }) => api<{ run_id: number; session_id: number; status: string }>(`/api/sessions/${sessionId}/runs`, token, { method: 'POST', body: JSON.stringify(body) })
export const cancelRun = (token: string, runId: number) => api<{ ok: boolean; run_id: number; status: string }>(`/api/runs/${runId}/cancel`, token, { method: 'POST' })
export const listEvents = (token: string, sessionId: number, afterSeq = 0) => api<{ events: RunEvent[] }>(`/api/sessions/${sessionId}/events?after_seq=${afterSeq}`, token)
