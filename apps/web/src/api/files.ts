import { api } from './client'
import type { FileEntry } from '../types'

const q = (s: string) => encodeURIComponent(s)

export const listTree = (token: string, slug: string, path = '') =>
  api<{ path: string; entries: FileEntry[] }>(`/api/projects/${slug}/tree?path=${q(path)}`, token)

export const projectWikiAll = (token: string, slug: string) =>
  api<{ notes: { path: string; content: string }[] }>(`/api/projects/${slug}/wiki/all`, token)

// Fetch raw file bytes (any type) as an object URL — for image preview / download.
export async function fetchRawBlob(token: string, slug: string, path: string): Promise<string> {
  const res = await fetch(`/api/projects/${slug}/raw?path=${q(path)}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error('download failed')
  return URL.createObjectURL(await res.blob())
}

export const readFile = (token: string, slug: string, path: string) =>
  api<{ path: string; content: string }>(`/api/projects/${slug}/file?path=${q(path)}`, token)

export const writeFile = (token: string, slug: string, path: string, content: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/file?path=${q(path)}`, token, { method: 'PUT', body: JSON.stringify({ content }) })

export const mkdir = (token: string, slug: string, path: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/fs/mkdir`, token, { method: 'POST', body: JSON.stringify({ path }) })

export const renamePath = (token: string, slug: string, from: string, to: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/fs/rename`, token, { method: 'POST', body: JSON.stringify({ from, to }) })

export const deletePath = (token: string, slug: string, path: string) =>
  api<{ ok: boolean }>(`/api/projects/${slug}/fs?path=${q(path)}`, token, { method: 'DELETE' })
