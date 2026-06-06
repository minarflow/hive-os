import { api } from './client'
import type { FileEntry } from '../types'

const q = (s: string) => encodeURIComponent(s)

// Personal per-user wiki (server jails it to users/<username>/wiki).
export const listTree = (token: string, path = '') =>
  api<{ path: string; entries: FileEntry[] }>(`/api/wiki/tree?path=${q(path)}`, token)

export const readFile = (token: string, path: string) =>
  api<{ path: string; content: string }>(`/api/wiki/file?path=${q(path)}`, token)

export const writeFile = (token: string, path: string, content: string) =>
  api<{ ok: boolean }>(`/api/wiki/file?path=${q(path)}`, token, { method: 'PUT', body: JSON.stringify({ content }) })

export const mkdir = (token: string, path: string) =>
  api<{ ok: boolean }>(`/api/wiki/fs/mkdir`, token, { method: 'POST', body: JSON.stringify({ path }) })

export const renamePath = (token: string, from: string, to: string) =>
  api<{ ok: boolean }>(`/api/wiki/fs/rename`, token, { method: 'POST', body: JSON.stringify({ from, to }) })

export const deletePath = (token: string, path: string) =>
  api<{ ok: boolean }>(`/api/wiki/fs?path=${q(path)}`, token, { method: 'DELETE' })
