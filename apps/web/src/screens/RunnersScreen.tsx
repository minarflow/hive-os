import type { Runner } from '../types'

export function RunnersScreen({ runners, onRefresh }: { token: string; runners: Runner[]; onRefresh: () => Promise<void> }) {
  return <section className="runners-view"><div className="panel runners-panel"><div className="panel-head"><div><h3>Runners</h3><p className="muted">Team Mode is Hermes-first. Other CLIs can be detected but are intentionally not executable yet.</p></div><button onClick={() => void onRefresh()}>Rescan</button></div><div className="runner-grid">{runners.map(runner => <article className={`runner-card ${runner.runnable ? 'ready' : runner.installed ? 'detected' : 'missing'}`} key={runner.id}><div className="runner-card-head"><strong>{runner.displayName}</strong><span>{runner.runnable ? 'Runnable' : runner.installed ? 'Future adapter' : 'Missing'}</span></div><small>{runner.id}</small><p>{runner.notes || 'No notes.'}</p><code>{runner.path || runner.binary || 'no binary detected'}</code></article>)}</div></div></section>
}
