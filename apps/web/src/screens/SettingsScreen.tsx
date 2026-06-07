import React from 'react'
import { changePassword } from '../api/auth'
import { listAudit, type AuditEntry } from '../api/audit'
import type { Profile, Project, User } from '../types'
import { THEMES, FONTS, FONT_SIZES, getTheme, getFont, getFontSize, applyTheme, applyFont, applyFontSize, type ThemeKey, type FontKey, type FontSizeKey } from '../theme'

const fmtTime = (s: string) => { try { return new Date(s.replace(' ', 'T') + (s.endsWith('Z') ? '' : 'Z')).toLocaleString() } catch { return s } }
const auditTone = (a: string) => /error|delete|remove|revoke/.test(a) ? 'danger' : /login|redeem|create|invite|provision/.test(a) ? 'accent' : ''

function AuditPanel({ token }: { token: string }) {
  const [entries, setEntries] = React.useState<AuditEntry[]>([])
  const [q, setQ] = React.useState('')
  const [error, setError] = React.useState('')
  const [open, setOpen] = React.useState(false)

  React.useEffect(() => { if (!open) return; listAudit(token).then(b => setEntries(b.entries)).catch(e => setError(String(e))) }, [token, open])

  const ql = q.trim().toLowerCase()
  const rows = ql ? entries.filter(e => `${e.actor} ${e.action} ${e.target_type} ${e.target_id} ${e.metadata}`.toLowerCase().includes(ql)) : entries

  return <div className="panel"><div className="panel-head"><h3>Audit log</h3><span>admin</span></div>
    <p className="muted">Every login, invite, run and admin action across the environment.</p>
    <button className="ghost-button" onClick={() => setOpen(true)}>Open audit log</button>
    {open && <div className="modal-scrim" onClick={() => setOpen(false)}><div className="modal-card audit-modal" onClick={e => e.stopPropagation()}>
      <div className="audit-modal-head"><h3>Audit log <span className="muted">({entries.length})</span></h3><button className="icon-button" aria-label="Close" onClick={() => setOpen(false)}>✕</button></div>
      <input className="ui-select audit-search" placeholder="Filter by actor, action, target…" value={q} onChange={e => setQ(e.target.value)} />
      <div className="audit-list scrollable">
        {rows.length === 0 && <p className="muted">No entries.</p>}
        {rows.map(e => <div className="audit-row" key={e.id}>
          <span className="audit-time">{fmtTime(e.created_at)}</span>
          <span className="audit-actor">{e.actor || 'system'}</span>
          <span className={`audit-action ${auditTone(e.action)}`}>{e.action}</span>
          <span className="audit-target" title={`${e.target_type}:${e.target_id}`}>{e.target_type}:{e.target_id}</span>
          {e.metadata && e.metadata !== '{}' ? <span className="audit-meta" title={e.metadata}>{e.metadata}</span> : <span />}
        </div>)}
      </div>
      {error && <p className="error-text">{error}</p>}
    </div></div>}
  </div>
}

export function SettingsScreen({ token, user, profiles, projects }: { token: string; user: User; profiles: Profile[]; projects: Project[] }) {
  const [theme, setTheme] = React.useState<ThemeKey>(getTheme())
  const [font, setFont] = React.useState<FontKey>(getFont())
  const [fontSize, setFontSize] = React.useState<FontSizeKey>(getFontSize())
  const [currentPassword, setCurrentPassword] = React.useState('')
  const [newPassword, setNewPassword] = React.useState('')
  const [confirmPassword, setConfirmPassword] = React.useState('')
  const [message, setMessage] = React.useState('')
  const [error, setError] = React.useState('')

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError(''); setMessage('')
    if (newPassword !== confirmPassword) return setError('New passwords do not match')
    try {
      const res = await changePassword(token, currentPassword, newPassword)
      setMessage(res.message)
      setCurrentPassword(''); setNewPassword(''); setConfirmPassword('')
    } catch (err) { setError(String(err)) }
  }

  return <section className="settings-view"><div className="panel"><div className="panel-head"><h3>Team Mode Settings</h3><span>PWA ready</span></div><div className="settings-grid"><div><p className="eyebrow">Signed in</p><h2>{user.username}</h2><p className="muted">{user.role}</p></div><div><p className="eyebrow">Hermes profiles</p><h2>{profiles.length}</h2><p className="muted">Every profile uses a separate managed HERMES_HOME.</p></div><div><p className="eyebrow">Visible projects</p><h2>{projects.length}</h2><p className="muted">Private/shared access is controlled by project membership.</p></div><div><p className="eyebrow">Install policy</p><h2>Local deps allowed</h2><p className="muted">Project-local dependency installs are allowed; global/system installs are blocked.</p></div></div></div><div className="panel"><div className="panel-head"><h3>Appearance</h3><span>theme &amp; font</span></div><p className="eyebrow">Theme</p><div className="theme-grid">{THEMES.map(t => <button key={t.key} className={`theme-swatch ${theme === t.key ? 'active' : ''}`} onClick={() => { applyTheme(t.key); setTheme(t.key) }} title={t.label} type="button"><span className="swatch-pv" style={{ background: t.surface }}><i style={{ background: t.accent }} /></span><small>{t.label}</small></button>)}</div><div className="settings-rows"><span className="srow-label">Font</span><select className="ui-select" value={font} onChange={e => { const f = e.target.value as FontKey; applyFont(f); setFont(f) }}>{FONTS.map(f => <option key={f.key} value={f.key} style={{ fontFamily: f.stack }}>{f.label}</option>)}</select><span className="srow-label">Font size</span><div className="seg sm fontsize-seg">{FONT_SIZES.map(s => <button type="button" key={s.key} className={fontSize === s.key ? 'active' : ''} onClick={() => { applyFontSize(s.key); setFontSize(s.key) }}>{s.label}</button>)}</div></div></div><div className="panel"><div className="panel-head"><h3>Change password</h3><span>self-service</span></div><form className="stack-form" onSubmit={submit}><label>Current password<input type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label><label>New password<input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label><label>Confirm new password<input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} /></label><button className="primary-button" disabled={!currentPassword || newPassword.length < 8}>Change password</button></form>{message && <p className="muted">{message}</p>}{error && <p className="error-text">{error}</p>}</div>{user.role === 'environment_admin' && <AuditPanel token={token} />}</section>
}
