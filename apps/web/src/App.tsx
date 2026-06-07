import React from 'react'
import { getSetupStatus, logout, me } from './api/auth'
import { listProfiles } from './api/profiles'
import { listProjects } from './api/projects'
import { listSessions, createSession, renameSession, deleteSession } from './api/sessions'
import { api } from './api/client'
import type { ChatSession, Profile, Project, Runner, User, View } from './types'
import { AppShell } from './components/shell/AppShell'
import { SetupScreen } from './screens/SetupScreen'
import { LoginScreen } from './screens/LoginScreen'
import { RedeemScreen } from './screens/RedeemScreen'
import { ChatScreen } from './screens/ChatScreen'
import { ProjectsScreen } from './screens/ProjectsScreen'
import { WikiScreen } from './screens/WikiScreen'
import { ArtifactsScreen } from './screens/ArtifactsScreen'
import { TasksScreen } from './screens/TasksScreen'
import { ProfilesScreen } from './screens/ProfilesScreen'
import { RunnersScreen } from './screens/RunnersScreen'
import { SettingsScreen } from './screens/SettingsScreen'
import { UsersScreen } from './screens/UsersScreen'

export function App() {
  const [booting, setBooting] = React.useState(true)
  const [needsSetup, setNeedsSetup] = React.useState(false)
  const [token, setToken] = React.useState(localStorage.getItem('hive-token') || '')
  const [user, setUser] = React.useState<User | null>(null)
  const [view, setView] = React.useState<View>('chat')
  const [pendingTask, setPendingTask] = React.useState<number | null>(null)
  const [pendingFile, setPendingFile] = React.useState<{ slug: string; path: string } | null>(null)
  const [profiles, setProfiles] = React.useState<Profile[]>([])
  const [projects, setProjects] = React.useState<Project[]>([])
  const [sessions, setSessions] = React.useState<ChatSession[]>([])
  const [runners, setRunners] = React.useState<Runner[]>([])
  const [activeProfile, setActiveProfile] = React.useState<Profile | null>(null)
  const [activeProject, setActiveProject] = React.useState<Project | null>(null)
  const [activeSession, setActiveSession] = React.useState<ChatSession | null>(null)
  const [error, setError] = React.useState('')

  const refreshAll = React.useCallback(async (authToken = token) => {
    if (!authToken) return
    const [profileBody, projectBody, sessionBody, runnerBody] = await Promise.all([
      listProfiles(authToken),
      listProjects(authToken),
      listSessions(authToken),
      api<{ runners: Runner[] }>('/api/runners/detect', authToken)
    ])
    setProfiles(profileBody.profiles)
    setProjects(projectBody.projects)
    setSessions(sessionBody.sessions)
    setRunners(runnerBody.runners)
    setActiveProfile(current => current && profileBody.profiles.some(p => p.id === current.id) ? current : profileBody.profiles.find(p => p.is_default) || profileBody.profiles[0] || null)
    setActiveProject(current => current && projectBody.projects.some(p => p.slug === current.slug) ? current : projectBody.projects[0] || null)
    setActiveSession(current => current && sessionBody.sessions.some(s => s.id === current.id) ? current : sessionBody.sessions[0] || null)
  }, [token])

  React.useEffect(() => {
    async function boot() {
      try {
        const setup = await getSetupStatus()
        setNeedsSetup(setup.bootstrap_required)
        if (token && !setup.bootstrap_required) {
          try {
            const current = await me(token)
            setUser(current)
            await refreshAll(token)
          } catch {
            // stale/expired token → drop it and fall back to the login screen
            localStorage.removeItem('hive-token'); setToken(''); setUser(null)
          }
        }
      } catch (err) {
        setError(String(err))
      } finally {
        setBooting(false)
      }
    }
    void boot()
  }, [refreshAll, token])

  async function acceptAuth(nextToken: string, nextUser: User) {
    localStorage.setItem('hive-token', nextToken)
    setToken(nextToken)
    setUser(nextUser)
    setNeedsSetup(false)
    await refreshAll(nextToken)
  }

  async function startNewSession() {
    const created = await createSession(token, { title: 'New chat', project_slug: activeProject?.slug || null, profile_id: activeProfile?.id || null })
    await refreshAll(token)
    setActiveSession(created)
    setView('chat')
  }

  async function handleRenameSession(id: number, title: string) {
    await renameSession(token, id, title)
    await refreshAll(token)
  }

  async function handleDeleteSession(id: number) {
    await deleteSession(token, id)
    setActiveSession(current => (current?.id === id ? null : current))
    await refreshAll(token)
  }

  async function doLogout() {
    if (token) await logout(token).catch(() => undefined)
    localStorage.removeItem('hive-token')
    setToken(''); setUser(null); setProfiles([]); setProjects([]); setSessions([]); setActiveProfile(null); setActiveProject(null); setActiveSession(null)
  }

  if (booting) return <div className="center-screen"><div className="brand-mark">H</div><p>Starting Hive OS…</p></div>
  if (needsSetup) return <SetupScreen onComplete={acceptAuth} />
  if (!token || !user) {
    const inviteCode = new URLSearchParams(window.location.search).get('invite')
    if (inviteCode) return <RedeemScreen code={inviteCode} onRedeemed={async (t, u) => { await acceptAuth(t, u); window.history.replaceState({}, '', window.location.pathname) }} />
    return <LoginScreen onLogin={acceptAuth} />
  }

  return (
    <AppShell
      activeProfile={activeProfile}
      activeProject={activeProject}
      activeSession={activeSession}
      currentView={view}
      onLogout={() => void doLogout()}
      onNewChat={() => void startNewSession()}
      onRenameSession={(id, title) => void handleRenameSession(id, title)}
      onDeleteSession={id => void handleDeleteSession(id)}
      onSelectProject={project => setActiveProject(project)}
      onSelectSession={session => { setActiveSession(session); setView('chat') }}
      onOpenTask={taskId => { setPendingTask(taskId); setView('tasks') }}
      onOpenFile={(slug, path) => { setPendingFile({ slug, path }); setView('artifacts') }}
      onSelectView={setView}
      profiles={profiles}
      projects={projects}
      sessions={sessions}
      token={token}
      user={user}
    >
      {error && <div className="error-bar">{error}</div>}
      {view === 'chat' && <ChatScreen activeProfile={activeProfile} activeProject={activeProject} activeSession={activeSession} profiles={profiles} projects={projects} token={token} onActiveProfile={setActiveProfile} onActiveProject={setActiveProject} onSession={setActiveSession} onRefresh={refreshAll} onNewSession={startNewSession} />}
      {view === 'projects' && <ProjectsScreen token={token} projects={projects} onActiveProject={setActiveProject} onRefresh={refreshAll} />}
      {view === 'wiki' && <WikiScreen token={token} projects={projects} />}
      {view === 'artifacts' && <ArtifactsScreen token={token} projects={projects} activeProject={activeProject} pendingFile={pendingFile} onPendingConsumed={() => setPendingFile(null)} />}
      {view === 'tasks' && <TasksScreen token={token} projects={projects} activeProject={activeProject} pendingTaskId={pendingTask} onPendingConsumed={() => setPendingTask(null)} />}
      {view === 'profiles' && <ProfilesScreen token={token} profiles={profiles} onActiveProfile={setActiveProfile} onRefresh={refreshAll} />}
      {view === 'runners' && <RunnersScreen runners={runners} token={token} onRefresh={refreshAll} />}
      {view === 'settings' && <SettingsScreen token={token} user={user} profiles={profiles} projects={projects} />}
      {view === 'users' && <UsersScreen token={token} user={user} onRefresh={refreshAll} />}
    </AppShell>
  )
}
