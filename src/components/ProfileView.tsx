import { useApp, albumStats } from '../state';
import { REGION_PRESETS, roundCoarse } from '../lib/geo';
import { useState } from 'react';

export function ProfileView() {
  const { catalog, album, profile, setProfile, clearAll, theme, setTheme } = useApp();
  const [editing, setEditing] = useState(false);
  const stats = albumStats(album, catalog);
  if (!profile) return null;

  const onExport = () => {
    const data = {
      profile, album,
      exportedAt: new Date().toISOString(),
      edition: catalog.edition,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `wc2026-album-${profile.alias.replace(/\s+/g, '-')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="stack-lg">
      <header className="card card-pad">
        <h2>Profile</h2>
        <div className="sub">Everything stays on this device.</div>
      </header>

      <div className="card card-pad stack">
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h3>Identity</h3>
          <button className="btn btn-sm" onClick={() => setEditing(e => !e)}>{editing ? 'Done' : 'Edit'}</button>
        </div>
        {editing ? (
          <Editor />
        ) : (
          <dl style={{ margin: 0, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 16px' }}>
            <dt className="muted" style={{ fontSize: 13 }}>Alias</dt><dd style={{ margin: 0 }}>{profile.alias}</dd>
            <dt className="muted" style={{ fontSize: 13 }}>Contact</dt><dd style={{ margin: 0 }}>{profile.email || <span className="muted">— none —</span>}</dd>
            <dt className="muted" style={{ fontSize: 13 }}>Region</dt><dd style={{ margin: 0 }}>{profile.region}{profile.coords ? ` · ~${profile.coords.lat.toFixed(1)}°, ${profile.coords.lng.toFixed(1)}°` : ''}</dd>
            <dt className="muted" style={{ fontSize: 13 }}>Trade matching</dt><dd style={{ margin: 0 }}>{profile.shareForTrades ? 'On' : 'Off'}</dd>
            <dt className="muted" style={{ fontSize: 13 }}>Consent given</dt><dd style={{ margin: 0 }}>{new Date(profile.consentAt).toLocaleString()}</dd>
          </dl>
        )}
      </div>

      <div className="card card-pad stack">
        <h3>Album summary</h3>
        <div className="kpi-grid">
          <div className="kpi"><div className="k-label">Owned</div><div className="k-value">{stats.owned}</div><div className="k-sub">{stats.completionPct.toFixed(1)}% complete</div></div>
          <div className="kpi"><div className="k-label">Missing</div><div className="k-value">{stats.missing}</div></div>
          <div className="kpi"><div className="k-label">Duplicates</div><div className="k-value">{stats.duplicates}</div></div>
          <div className="kpi"><div className="k-label">Total set</div><div className="k-value">{catalog.total}</div></div>
        </div>
      </div>

      <div className="card card-pad stack">
        <h3>Appearance</h3>
        <div className="filter-row">
          {(['system','light','dark'] as const).map(t => (
            <button key={t} className="chip" aria-pressed={theme === t} onClick={() => setTheme(t)}>{t[0].toUpperCase() + t.slice(1)}</button>
          ))}
        </div>
      </div>

      <div className="card card-pad stack">
        <h3>Your data</h3>
        <p className="muted" style={{ margin: 0, fontSize: 13.5 }}>
          This app keeps your album in your browser's local storage. Nothing is sent anywhere automatically in the static GitHub Pages build. The only path that leaves your device is opening a GitHub issue yourself to publish a trade profile — a maintainer reviews it and a GitHub Actions workflow commits the entry. Export your data below for a portable JSON backup.
        </p>
        <div className="row gap-2" style={{ flexWrap: 'wrap' }}>
          <button className="btn" onClick={onExport}>Export my data (JSON)</button>
          <button className="btn btn-danger" onClick={() => {
            if (confirm('Clear all locally stored data, including your album and profile? This cannot be undone.')) {
              clearAll();
            }
          }}>Clear all data</button>
          <button className="btn btn-ghost" onClick={() => { if (confirm('Sign out keeps your album but clears your profile so you can re-onboard. Continue?')) setProfile(null); }}>Sign out</button>
        </div>
      </div>
    </div>
  );
}

function Editor() {
  const { profile, setProfile } = useApp();
  const [alias, setAlias] = useState(profile?.alias ?? '');
  const [email, setEmail] = useState(profile?.email ?? '');
  const [region, setRegion] = useState(profile?.region ?? REGION_PRESETS[0].label);
  const [coords, setCoords] = useState(profile?.coords);
  const [share, setShare] = useState(profile?.shareForTrades ?? true);

  return (
    <div className="stack">
      <div className="field">
        <label>Alias</label>
        <input className="input" value={alias} onChange={e => setAlias(e.target.value)} maxLength={40}/>
      </div>
      <div className="field">
        <label>Contact</label>
        <input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} maxLength={120}/>
      </div>
      <div className="field">
        <label>Region</label>
        <select className="select" value={region} onChange={e => {
          setRegion(e.target.value);
          const f = REGION_PRESETS.find(p => p.label === e.target.value);
          setCoords(f?.coords);
        }}>
          {REGION_PRESETS.map(p => <option key={p.label} value={p.label}>{p.label}</option>)}
        </select>
        <button type="button" className="btn btn-sm mt-2" onClick={() => {
          navigator.geolocation?.getCurrentPosition(
            pos => setCoords(roundCoarse(pos.coords.latitude, pos.coords.longitude)),
            () => {}
          );
        }}>Use browser location (rounded)</button>
      </div>
      <label className="check">
        <input type="checkbox" checked={share} onChange={e => setShare(e.target.checked)} />
        <span>Include me in trade matching</span>
      </label>
      <button className="btn btn-primary" onClick={() => {
        if (!profile) return;
        setProfile({ ...profile, alias: alias.trim() || profile.alias, email: email.trim(), region, coords, shareForTrades: share });
      }}>Save changes</button>
    </div>
  );
}
