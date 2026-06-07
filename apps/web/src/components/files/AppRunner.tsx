import React from 'react'
import { appStart, appStop, appStatus, appViewUrl, type AppStatus } from '../../api/files'

// Run a project's dev server as a managed process and preview it live (proxied).
export function AppRunner({ token, slug, onClose }: { token: string; slug: string; onClose: () => void }) {
  const [command, setCommand] = React.useState(() => localStorage.getItem('hive.appcmd.' + slug) || 'npm run dev')
  const [port, setPort] = React.useState(() => Number(localStorage.getItem('hive.appport.' + slug)) || 5180)
  const [status, setStatus] = React.useState<AppStatus>({ running: false })
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState('')
  const [reloadKey, setReloadKey] = React.useState(0)

  const poll = React.useCallback(() => { appStatus(token, slug).then(setStatus).catch(() => {}) }, [token, slug])
  React.useEffect(() => { poll(); const t = window.setInterval(poll, 2000); return () => clearInterval(t) }, [poll])

  async function run() {
    setError(''); setBusy(true)
    localStorage.setItem('hive.appcmd.' + slug, command); localStorage.setItem('hive.appport.' + slug, String(port))
    try { await appStart(token, slug, command, port); window.setTimeout(() => setReloadKey(k => k + 1), 1800); poll() }
    catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  async function stop() { setBusy(true); try { await appStop(token, slug); poll() } catch (e) { setError(String(e)) } finally { setBusy(false) } }

  return <div className="modal-scrim" onClick={onClose}><div className="modal-card app-runner" onClick={e => e.stopPropagation()}>
    <div className="app-runner-head"><strong>Run &amp; Preview app</strong><button className="icon-button" onClick={onClose} aria-label="Close">✕</button></div>
    <div className="app-runner-bar">
      <input className="ui-select" value={command} onChange={e => setCommand(e.target.value)} placeholder="npm run dev" />
      <input className="ui-select app-port" type="number" value={port} onChange={e => setPort(Number(e.target.value) || 5180)} title="Server harus listen di port ini ($PORT)" />
      {status.running
        ? <><button className="ghost-button" onClick={() => setReloadKey(k => k + 1)}>Reload</button><button className="ghost-button danger" onClick={() => void stop()} disabled={busy}>Stop</button></>
        : <button className="primary-button" onClick={() => void run()} disabled={busy || !command.trim()}>▶ Run</button>}
    </div>
    {error && <p className="error-text">{error}</p>}
    <div className="app-runner-body">
      {status.running
        ? <iframe key={reloadKey} className="app-frame" title="App preview" src={appViewUrl(token, slug)} sandbox="allow-scripts allow-same-origin allow-forms allow-popups" />
        : <div className="app-runner-log">
            <p className="muted">{status.exited ? 'App berhenti — cek log di bawah.' : 'Masukin command (mis. `npm run dev` / `python app.py`) + port, terus Run. Server-nya harus listen di port itu (tersedia juga sebagai $PORT).'}</p>
            {(status.log || []).length > 0 && <pre className="app-log">{(status.log || []).join('\n')}</pre>}
          </div>}
    </div>
    {status.running && <p className="muted app-runner-tip">Live di app. Mau dari HP/Tailscale? jalanin: <code>tailscale serve --bg https / http://127.0.0.1:{port}</code></p>}
  </div></div>
}
