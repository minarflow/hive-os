export type User = { id: number; username: string; role: string; os_user: string }
export type Profile = { id: number; slug: string; name: string; default_model?: string | null; is_default: boolean; hermes_home?: string }
export type Project = { slug: string; name: string; path: string; owner: string; role: string; visibility: 'private' | 'shared' }
export type Runner = { id: string; displayName: string; installed: boolean; path?: string | null; binary?: string | null; hasAdapter: boolean; detectionOnly: boolean; runnable: boolean; notes?: string }
export type ChatSession = { id: number; title: string; runner_id: string; profile_id?: number | null; profile_slug?: string | null; profile_name?: string | null; project_slug?: string | null; project_name?: string | null; visibility: 'private' | 'project'; updated_at?: string }
export type ChatMessage = { id?: number; role: 'user' | 'system' | 'assistant'; content: string; created_at?: string }
export type RunEvent = { id: number; seq: number; type: string; run_id: number; session_id: number; project_id?: number | null; payload: Record<string, unknown>; created_at: string }
export type View = 'chat' | 'projects' | 'linc-projects' | 'profiles' | 'runners' | 'settings' | 'users'
