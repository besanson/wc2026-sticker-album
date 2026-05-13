import { useMemo, useState } from 'react';
import { useApp } from '../state';
import { findTrades } from '../lib/trade';
import type { TradeMatch } from '../lib/trade';

const DIST_OPTIONS = [
  { label: 'In your city (<50 km)', km: 50 },
  { label: 'Same region (<200 km)', km: 200 },
  { label: 'Same country (<800 km)', km: 800 },
  { label: 'Same continent (<2,500 km)', km: 2500 },
  { label: 'Worldwide', km: 99999 },
];

export function TradesView() {
  const { catalog, album, users, profile, proposedTradeAcceptances, toggleTradeAcceptance } = useApp();
  const [maxDistance, setMaxDistance] = useState(2500);
  const [minScore, setMinScore] = useState(15);
  const [openId, setOpenId] = useState<string | null>(null);
  const [demoEnabled, setDemoEnabled] = useState(false);

  const matches = useMemo(() => {
    return findTrades(album, catalog, users, profile?.coords, { maxDistanceKm: maxDistance, minScore });
  }, [album, catalog, users, profile, maxDistance, minScore]);

  return (
    <div className="stack-lg">
      <header className="card card-pad">
        <h2>Trades nearby</h2>
        <div className="sub">
          Matched on overlap of your duplicates against another collector's missing list and vice-versa, with a coarse distance preference. Exact locations are never shared — only a distance bucket.
        </div>
        <div className="notice mt-4">
          <b>Privacy-first trade network.</b> This static GitHub Pages build is not connected to real collectors yet. To test the matching algorithm, you can turn on demo collector data below; otherwise no people are shown.
        </div>
        <div className="row gap-3 mt-4" style={{ flexWrap: 'wrap' }}>
          <button className={`btn ${demoEnabled ? '' : 'btn-primary'}`} onClick={() => setDemoEnabled(!demoEnabled)}>
            {demoEnabled ? 'Hide demo collectors' : 'Show demo collectors'}
          </button>
          <div className="field" style={{ minWidth: 220 }}>
            <label>Distance</label>
            <select className="select" value={maxDistance} onChange={e => setMaxDistance(Number(e.target.value))} disabled={!demoEnabled}>
              {DIST_OPTIONS.map(o => <option key={o.km} value={o.km}>{o.label}</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 180 }}>
            <label>Min match score</label>
            <select className="select" value={minScore} onChange={e => setMinScore(Number(e.target.value))} disabled={!demoEnabled}>
              {[0, 15, 30, 45, 60].map(n => <option key={n} value={n}>{n}+</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 140 }}>
            <label>Results</label>
            <div className="tabular" style={{ paddingTop: 8, fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700 }}>{demoEnabled ? matches.length : 0}</div>
          </div>
        </div>
      </header>

      {!demoEnabled ? (
        <div className="card card-pad muted" style={{ textAlign: 'center' }}>
          Real trade matching needs a connected user database or serverless endpoint. In production, this screen would query opted-in collectors only, using coarse region data and never precise coordinates.
        </div>
      ) : matches.length === 0 ? (
        <div className="card card-pad muted" style={{ textAlign: 'center' }}>
          No matches yet. Mark some stickers as duplicates (count &gt; 1) and add what you're missing to start matching.
        </div>
      ) : (
        <div className="trade-card">
          <div className="demo-banner">
            Demo mode: the collectors below are generated test profiles used only to demonstrate scoring. They are not real accounts.
          </div>
          {matches.slice(0, 24).map(m => (
            <TradeRow
              key={m.user.id}
              match={m}
              expanded={openId === m.user.id}
              accepted={proposedTradeAcceptances.includes(m.user.id)}
              onToggleExpand={() => setOpenId(openId === m.user.id ? null : m.user.id)}
              onToggleAccept={() => toggleTradeAcceptance(m.user.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TradeRow({ match, expanded, accepted, onToggleExpand, onToggleAccept }: {
  match: TradeMatch; expanded: boolean; accepted: boolean; onToggleExpand: () => void; onToggleAccept: () => void;
}) {
  const { user, iCanGive, iCanReceive, score, components, distanceLabel } = match;
  const initials = user.alias.split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase();

  return (
    <div className="trade-row">
      <div className="trade-user">
        <div className="row gap-3" style={{ marginBottom: 6 }}>
          <div className="avatar" style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--surface-3)', display: 'grid', placeItems: 'center', fontWeight: 700, color: 'var(--text)' }}>{initials}</div>
          <div>
            <div className="alias">{user.alias}</div>
            <div className="region">{user.region}</div>
          </div>
        </div>
        <div className="meta">
          Demo collector · {distanceLabel} · {user.completionPct}% complete
        </div>
      </div>

      <div className="trade-stats">
        <div className="row"><span>You can give</span><b className="tabular">{iCanGive.length} stickers</b></div>
        <div className="row"><span>You can receive</span><b className="tabular">{iCanReceive.length} stickers</b></div>
        <div className="row muted"><span>Match balance</span><span className="tabular">{Math.round(components.balance * 100)}%</span></div>
        <div className="row muted"><span>Distance weight</span><span className="tabular">{Math.round(components.distance * 100)}%</span></div>
        {expanded && (
          <div className="trade-explainer mt-2">
            <div><b>Score formula:</b> <code>0.55·overlap + 0.20·balance + 0.18·distance + 0.07·activity</code></div>
            <div className="mt-2">
              Overlap <code>{(components.overlap).toFixed(2)}</code> · Balance <code>{components.balance.toFixed(2)}</code> · Distance <code>{components.distance.toFixed(2)}</code> · Activity <code>{components.activity.toFixed(2)}</code>
            </div>
            <div className="mt-2 muted">
              This is generated demo data, not a real account. Wire <code>/api/users</code> to replace it with opted-in collectors.
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gap: 8, justifyItems: 'end' }}>
        <div className="trade-score" aria-label={`Score ${score}`}>{score}</div>
        <button className="btn btn-sm" onClick={onToggleExpand}>{expanded ? 'Hide details' : 'Why this match?'}</button>
        <button className={`btn btn-sm ${accepted ? '' : 'btn-primary'}`} onClick={onToggleAccept}>
          {accepted ? 'Demo selected ✓' : 'Test demo trade'}
        </button>
      </div>
    </div>
  );
}
