import { api } from './client'
import type { Profile, User } from '../types'

export type Invite = { code: string; role: string; expires_at: string | null; used_at: string | null; used_by: string | null }

export const createInvite = (token: string, role: 'member' | 'admin', expires_in_hours: number) =>
  api<{ code: string; role: string; expires_at: string }>('/api/invites', token, { method: 'POST', body: JSON.stringify({ role, expires_in_hours }) })

export const listInvites = (token: string) => api<{ invites: Invite[] }>('/api/invites', token)

export const revokeInvite = (token: string, code: string) =>
  api<{ ok: boolean }>(`/api/invites/${encodeURIComponent(code)}`, token, { method: 'DELETE' })

// Public (no auth) — used by the redeem screen.
export const previewInvite = (code: string) =>
  api<{ valid: boolean; role: string }>(`/api/invites/${encodeURIComponent(code)}`)

export const redeemInvite = (code: string, body: { username: string; password: string; profile_name: string }) =>
  api<{ token: string; user: User; profile: Profile }>(`/api/invites/${encodeURIComponent(code)}/redeem`, undefined, { method: 'POST', body: JSON.stringify(body) })
