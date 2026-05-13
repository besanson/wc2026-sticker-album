import { useState } from 'react';
import { useApp } from '../state';
import { Logo } from './Logo';
import { REGION_PRESETS, roundCoarse } from '../lib/geo';
import type { Profile } from '../types';

export function Onboarding() {
  const { setProfile } = useApp();
  const [alias, setAlias] = useState('');
  const [email, setEmail] = useState('');
  const [region, setRegion] = useState(REGION_PRESETS[0].label);
  const [coords, setCoords] = useState<{ lat: number; lng: number } | undefined>(REGION_PRESETS[0].coords);
  const [shareForTrades, setShareForTrades] = useState(true);
  const [consent, setConsent] = useState(false);
  const [geoError, setGeoError] = useState<string | null>(null);
  const [geoStatus, setGeoStatus] = useState<'idle' | 'loading' | 'done'>('idle');

  const onPickRegion = (label: string) => {
    setRegion(label);
    const found = REGION_PRESETS.find(p => p.label === label);
    setCoords(found?.coords);
  };

  const onUseBrowserGeo = () => {
    if (!navigator.geolocation) { setGeoError('Geolocation not available in this browser'); return; }
    setGeoStatus('loading');
    setGeoError(null);
    navigator.geolocation.getCurrentPosition(
      pos => {
        const coarse = roundCoarse(pos.coords.latitude, pos.coords.longitude);
        setCoords(coarse);
        setGeoStatus('done');
      },
      err => { setGeoError(err.message || 'Location request denied'); setGeoStatus('idle'); },
      { enableHighAccuracy: false, maximumAge: 60_000, timeout: 8000 }
    );
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!alias.trim() || !consent) return;
    const profile: Profile = {
      alias: alias.trim().slice(0, 40),
      email: email.trim().slice(0, 120),
      region,
      coords,
      consentAt: new Date().toISOString(),
      shareForTrades,
      createdAt: new Date().toISOString(),
    };
    setProfile(profile);
  };

  return (
    <div className="onboard">
      <form className="card card-pad onboard-card stack" onSubmit={submit}>
        <div className="row gap-3" style={{ color: 'var(--accent)' }}>
          <Logo size={36} />
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 22, color: 'var(--text)' }}>Estádio</div>
            <div className="brand-tag">2026 World Cup sticker album</div>
          </div>
        </div>

        <p className="muted" style={{ margin: 0 }}>
          Track every sticker, swap doubles with collectors nearby, and forecast how close you are to a full set.
        </p>

        <div className="field">
          <label htmlFor="alias">Display name</label>
          <input id="alias" className="input" placeholder="e.g. Goalden Boot" value={alias} onChange={e => setAlias(e.target.value)} required maxLength={40} />
        </div>

        <div className="field">
          <label htmlFor="email">Contact (optional)</label>
          <input id="email" type="email" className="input" placeholder="how trades reach you — kept on this device" value={email} onChange={e => setEmail(e.target.value)} maxLength={120} />
        </div>

        <div className="field">
          <label htmlFor="region">Region</label>
          <select id="region" className="select" value={region} onChange={e => onPickRegion(e.target.value)}>
            {REGION_PRESETS.map(p => <option key={p.label} value={p.label}>{p.label}</option>)}
          </select>
          <div className="row gap-2 mt-2" style={{ flexWrap: 'wrap' }}>
            <button type="button" className="btn btn-sm" onClick={onUseBrowserGeo} disabled={geoStatus === 'loading'}>
              {geoStatus === 'loading' ? 'Locating…' : geoStatus === 'done' ? 'Location rounded' : 'Use browser location (rounded)'}
            </button>
            {coords && <span className="muted" style={{ fontSize: 12 }}>~{coords.lat.toFixed(1)}°, {coords.lng.toFixed(1)}° · rounded to ~55 km</span>}
          </div>
          {geoError && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{geoError}</div>}
        </div>

        <label className="check">
          <input type="checkbox" checked={shareForTrades} onChange={e => setShareForTrades(e.target.checked)} />
          <span>
            Include me in trade matching nearby other collectors
            <span className="small">Only your alias, region, and which stickers you'd swap are used — no exact location.</span>
          </span>
        </label>

        <div className="privacy-note">
          <b>How your data is handled.</b> Everything in this app lives on your device. Nothing is sent to a server in the static build. Location is stored as a coarse city pick or rounded to ~55 km if you use browser geolocation. You can export or clear all data at any time from <i>Profile</i>.
        </div>

        <label className="check">
          <input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required />
          <span>
            I understand and consent (GDPR Article 6(1)(a))
            <span className="small">By checking this box you agree to local storage of the data above. Withdraw at any time by clearing data.</span>
          </span>
        </label>

        <button type="submit" className="btn btn-primary" disabled={!alias.trim() || !consent}>Open the album</button>
      </form>
    </div>
  );
}
