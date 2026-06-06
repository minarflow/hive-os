import React from 'react'
import { changePassword } from '../api/auth'
import type { Profile, Project, User } from '../types'
import { THEMES, FONTS, FONT_SIZES, getTheme, getFont, getFontSize, applyTheme, applyFont, applyFontSize, type ThemeKey, type FontKey, type FontSizeKey } from '../theme'

export function SettingsScreen({ token, user, profiles, projects, onLogout }: { token: string; user: User; profiles: Profile[]; projects: Project[]; onLogout: () => void }) {
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

  return <section className="settings-view"><div className="panel"><div className="panel-head"><h3>Team Mode Settings</h3><span>PWA ready</span></div><div className="settings-grid"><div><p className="eyebrow">Signed in</p><h2>{user.username}</h2><p className="muted">{user.role}</p></div><div><p className="eyebrow">Hermes profiles</p><h2>{profiles.length}</h2><p className="muted">Every profile uses a separate managed HERMES_HOME.</p></div><div><p className="eyebrow">Visible projects</p><h2>{projects.length}</h2><p className="muted">Private/shared access is controlled by project membership.</p></div><div><p className="eyebrow">Install policy</p><h2>Local deps allowed</h2><p className="muted">Project-local dependency installs are allowed; global/system installs are blocked.</p></div></div></div><div className="panel"><div className="panel-head"><h3>Appearance</h3><span>theme &amp; font</span></div><p className="eyebrow">Theme</p><div className="theme-grid">{THEMES.map(t => <button key={t.key} className={`theme-swatch ${theme === t.key ? 'active' : ''}`} onClick={() => { applyTheme(t.key); setTheme(t.key) }} title={t.label} type="button"><span className="swatch-pv" style={{ background: t.surface }}><i style={{ background: t.accent }} /></span><small>{t.label}</small></button>)}</div><div className="settings-rows"><span className="srow-label">Font</span><select className="ui-select" value={font} onChange={e => { const f = e.target.value as FontKey; applyFont(f); setFont(f) }}>{FONTS.map(f => <option key={f.key} value={f.key} style={{ fontFamily: f.stack }}>{f.label}</option>)}</select><span className="srow-label">Font size</span><div className="seg sm fontsize-seg">{FONT_SIZES.map(s => <button type="button" key={s.key} className={fontSize === s.key ? 'active' : ''} onClick={() => { applyFontSize(s.key); setFontSize(s.key) }}>{s.label}</button>)}</div></div></div><div className="panel"><div className="panel-head"><h3>Change password</h3><span>self-service</span></div><form className="stack-form" onSubmit={submit}><label>Current password<input type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} /></label><label>New password<input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} /></label><label>Confirm new password<input type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} /></label><button className="primary-button" disabled={!currentPassword || newPassword.length < 8}>Change password</button></form>{message && <p className="muted">{message}</p>}{error && <p className="error-text">{error}</p>}</div><div className="panel"><div className="panel-head"><h3>Account</h3><span>{user.username}</span></div><p className="muted">Sign out of this device. Your session token will be revoked.</p><button className="logout-button" onClick={onLogout}>Logout</button></div></section>
}
