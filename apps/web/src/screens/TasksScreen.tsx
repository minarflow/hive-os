import React from 'react'
import type { Project, Task, TaskStatus } from '../types'
import { listTasks, createTask, getTask, updateTask, deleteTask } from '../api/tasks'
import { TaskChat } from '../components/tasks/TaskChat'

const COLUMNS: { key: TaskStatus; label: string }[] = [
  { key: 'todo', label: 'To do' },
  { key: 'doing', label: 'In progress' },
  { key: 'review', label: 'Review' },
  { key: 'done', label: 'Done' }
]
const clean = (n: string) => n.replace(/\s*\(private\)\s*$/i, '')

function TaskDetail({ token, task, onBack, onStatus, onDelete }: { token: string; task: Task; onBack: () => void; onStatus: (t: Task, s: TaskStatus) => void; onDelete: (t: Task) => void }) {
  return <div className="task-detail">
    <div className="task-detail-head">
      <button className="ghost-button" onClick={onBack}>← Board</button>
      <strong className="task-title" title={task.title}>{task.title}</strong>
      <div className="seg sm task-status-seg">{COLUMNS.map(c => <button key={c.key} className={task.status === c.key ? 'active' : ''} onClick={() => onStatus(task, c.key)}>{c.label}</button>)}</div>
      <button className="ghost-button danger" onClick={() => onDelete(task)}>Delete</button>
    </div>
    {task.description && <p className="task-desc">{task.description}</p>}
    {task.session_id ? <div className="task-thread"><TaskChat token={token} sessionId={task.session_id} /></div> : <p className="muted" style={{ padding: 16 }}>No thread linked.</p>}
  </div>
}

export function TasksScreen({ token, projects, activeProject, pendingTaskId, onPendingConsumed }: { token: string; projects: Project[]; activeProject: Project | null; pendingTaskId?: number | null; onPendingConsumed?: () => void }) {
  const [slug, setSlug] = React.useState(activeProject?.slug || projects[0]?.slug || '')
  const [tasks, setTasks] = React.useState<Task[]>([])
  const [selected, setSelected] = React.useState<Task | null>(null)
  const [error, setError] = React.useState('')
  const project = projects.find(p => p.slug === slug) || null

  const reload = React.useCallback(async () => {
    if (!project) { setTasks([]); return }
    setTasks((await listTasks(token, project.slug)).tasks)
  }, [token, project?.slug])

  React.useEffect(() => { setSelected(null); void reload().catch(e => setError(String(e))) }, [reload])

  // Open a specific task when navigated from the sidebar.
  React.useEffect(() => {
    if (!pendingTaskId) return
    getTask(token, pendingTaskId).then(t => { if (t.project_slug) setSlug(t.project_slug); setSelected(t) }).catch(e => setError(String(e))).finally(() => onPendingConsumed?.())
  }, [pendingTaskId])

  async function create() {
    const title = window.prompt('New task title')?.trim()
    if (!title || !project) return
    try { const t = await createTask(token, project.slug, { title }); await reload(); setSelected(t) } catch (e) { setError(String(e)) }
  }
  async function setStatus(t: Task, status: TaskStatus) {
    try { const u = await updateTask(token, t.id, { status }); setTasks(cur => cur.map(x => x.id === t.id ? u : x)); if (selected?.id === t.id) setSelected(u) } catch (e) { setError(String(e)) }
  }
  async function remove(t: Task) {
    if (!window.confirm(`Delete task "${t.title}"? Its thread will be removed too.`)) return
    try { await deleteTask(token, t.id); setSelected(null); await reload() } catch (e) { setError(String(e)) }
  }

  if (projects.length === 0) return <section className="placeholder-view"><div className="assistant-bubble compact"><h1>Tasks</h1><p>No projects yet.</p></div></section>

  if (selected) return <section className="tasks-view"><TaskDetail token={token} task={selected} onBack={() => setSelected(null)} onStatus={setStatus} onDelete={remove} /></section>

  return <section className="tasks-view">
    <div className="tasks-head">
      <select className="ui-select" value={slug} onChange={e => setSlug(e.target.value)}>{projects.map(p => <option key={p.slug} value={p.slug}>{clean(p.name)}</option>)}</select>
      <button className="primary-button" onClick={() => void create()}>New task</button>
    </div>
    {error && <div className="error-bar">{error}</div>}
    <div className="kanban">{COLUMNS.map(col => {
      const items = tasks.filter(t => t.status === col.key)
      return <div className="kanban-col" key={col.key}>
        <div className="kanban-col-head"><span>{col.label}</span><span className="kanban-count">{items.length}</span></div>
        <div className="kanban-cards">{items.map(t => <button className="kanban-card" key={t.id} onClick={() => setSelected(t)}>
          <strong>{t.title}</strong>
          {(t.assignee || t.description) && <small>{t.assignee || t.description.slice(0, 60)}</small>}
        </button>)}</div>
      </div>
    })}</div>
  </section>
}
