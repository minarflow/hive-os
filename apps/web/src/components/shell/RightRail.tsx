import type { ChatSession, Profile, Project } from '../../types'
import { WorkspaceTree } from '../files/WorkspaceTree'

export function RightRail({ token, activeProject }: { token: string; activeProfile: Profile | null; activeProject: Project | null; activeSession: ChatSession | null; projects: Project[] }) {
  return <WorkspaceTree token={token} project={activeProject} />
}
