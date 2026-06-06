export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...((options.headers as Record<string, string>) || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(path, { ...options, headers })
  if (!res.ok) {
    const text = await res.text()
    try {
      const parsed = JSON.parse(text) as { detail?: string }
      throw new ApiError(res.status, parsed.detail || text)
    } catch (err) {
      if (err instanceof ApiError) throw err
      throw new ApiError(res.status, text || res.statusText)
    }
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}
