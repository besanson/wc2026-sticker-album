import { useEffect, useMemo, useState } from 'react';
import { useApp } from '../state';
import { findTrades } from '../lib/trade';
import type { TradeMatch } from '../lib/trade';
import type { SimUser } from '../types';
import {
  buildIssueUrl,
  buildRemovalUrl,
  loadTradeNetwork,
  profileToSimUser,
  type TradeNetworkDB,
} from '../lib/tradeNetwork';

const DIST_OPTIONS = [
  { label: 'In your city (<50 km)', km: 50 },
  { label: 'Same region (<200 km)', km: 200 },
  { label: 'Same country (<800 km)', km: 800 },
  { label: 'Same continent (<2,500 km)', km: 2500 },
  { label: 'Worldwide', km: 99999 },
];

const REPO_SLUG = (import.meta.env.VITE_REPO_SLUG as string | undefined) ?? '';

export function TradesView() {
  const { catalog, album, users: demoUsers, profile, proposedTradeAcceptances, toggleTradeAcceptance } = useApp();
  const [maxDistance, setMaxDistance] = useState(2500);
  const [minScore, setMinScore] = useState(15);
  const [openId, setOpenId] = useState<string | null>(null);
  const [demoEnabled, setDemoEnabled] = useState(false);
  const [network, setNetwork] = useState<TradeNetworkDB | null>(null);
  const [loadState, setLoadState] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [loadError, setLoadError] = useState<string>('');

  useEffect(() => {
    let cancelled = false;
    setLoadState('loading');
    loadTradeNetwork(import.meta.env.BASE_URL)
      .then(db => {
        if (cancelled) return;
        setNetwork(db);
        setLoadState('ready');
      })
      .catch(err => {
        if (cancelled) return;
        setLoadError(err?.message ?? String(err));
        setLoadState('error');
      });
    return () => { cancelled = true; };
  }, []);

  const publishedUsers: SimUser[] = useMemo(() => {
    if (!network) return [];
    return network.profiles.map(p => profileToSimUser(p, catalog.total));
  }, [network, catalog.total]);

  const usersForMatching = demoEnabled ? demoUsers : publishedUsers;

  const matches = useMemo(() => {
    return findTrades(album, catalog, usersForMatching, profile?.coords, { maxDistanceKm: maxDistance, minScore });
  }, [album, catalog, usersForMatching, profile, maxDistance, minScore]);

  const issueUrl = buildIssueUrl(REPO_SLUG);
  const removalUrl = buildRemovalUrl(REPO_SLUG);
  const hasPublished = publishedUsers.length > 0;

  return (
    <div className="stack-lg">
      <header className="card card-pad">
        <h2>Trades</h2>
        <div className="sub">
          Matched on overlap of your duplicates against another collector's missing list and vice-versa, with a coarse distance preference. Exact locations are never shared — only a distance bucket.
        </div>

        <div className="notice mt-4">
          <b>You need a GitHub account to publish a trade profile.</b> This site is a
          static GitHub Pages build with no server and no database — the only way to
          add yourself to the trade ledger is by opening an issue on the project's
          GitHub repository. You will be prompted to sign in with GitHub if you are
          not already.
          <ol className="trade-flow">
            <li><b>Sign in to GitHub</b> and open the <i>Publish a trade profile</i> issue template.</li>
            <li>Fill in your alias, a coarse region, the sticker IDs you're missing and the duplicates you'd swap, and tick the two consent boxes.</li>
            <li>A maintainer reviews the issue. If it looks reasonable, they add the <code>approved</code> label.</li>
            <li>A <b>GitHub Actions workflow</b> — not you — then validates the submission and commits your entry to <code>public/trade-network.json</code> on <code>main</code>. The Pages deploy publishes the new file a minute or two later.</li>
            <li>Your browser fetches that file directly on next load. No API, no auth token in the frontend, no precise location.</li>
          </ol>
          Removal works the same way: open the removal issue template and a maintainer approves it.
        </div>

        <div className="row gap-3 mt-4" style={{ flexWrap: 'wrap' }}>
          <a className="btn btn-primary" href={issueUrl} target="_blank" rel="noopener noreferrer">
            Sign in with GitHub & publish profile
          </a>
          <a className="btn" href={removalUrl} target="_blank" rel="noopener noreferrer">
            Request profile removal
          </a>
          <button className="btn" onClick={() => setDemoEnabled(v => !v)} aria-pressed={demoEnabled}>
            {demoEnabled ? 'Hide developer demo data' : 'Show developer demo data'}
          </button>
        </div>
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          No GitHub account? You can still use the album, forecast, and demo trade
          matching locally — only publishing a real trade profile requires GitHub.
        </div>

        <div className="row gap-3 mt-4" style={{ flexWrap: 'wrap' }}>
          <div className="field" style={{ minWidth: 220 }}>
            <label>Distance</label>
            <select className="select" value={maxDistance} onChange={e => setMaxDistance(Number(e.target.value))}>
              {DIST_OPTIONS.map(o => <option key={o.km} value={o.km}>{o.label}</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 180 }}>
            <label>Min match score</label>
            <select className="select" value={minScore} onChange={e => setMinScore(Number(e.target.value))}>
              {[0, 15, 30, 45, 60].map(n => <option key={n} value={n}>{n}+</option>)}
            </select>
          </div>
          <div className="field" style={{ minWidth: 140 }}>
            <label>Results</label>
            <div className="tabular" style={{ paddingTop: 8, fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 700 }}>{matches.length}</div>
          </div>
          <div className="field" style={{ minWidth: 220 }}>
            <label>Source</label>
            <div className="tabular muted" style={{ paddingTop: 8 }}>
              {demoEnabled
                ? `Demo data · ${demoUsers.length} generated profiles`
                : loadState === 'loading'
                  ? 'Loading published profiles…'
                  : loadState === 'error'
                    ? 'Failed to load'
                    : `${publishedUsers.length} GitHub-published profile${publishedUsers.length === 1 ? '' : 's'}`}
            </div>
          </div>
        </div>
      </header>

      {!demoEnabled && loadState === 'error' && (
        <div className="card card-pad muted" style={{ textAlign: 'center' }}>
          Could not load <code>trade-network.json</code>: {loadError}. The file is generated from approved GitHub issues. Maintainers: ensure <code>public/trade-network.json</code> exists.
        </div>
      )}

      {!demoEnabled && loadState === 'ready' && !hasPublished && (
        <div className="card card-pad empty-state">
          <div className="empty-illustration" aria-hidden="true">⚽</div>
          <h3>No published trade profiles yet</h3>
          <p className="muted">
            Be the first. Sign in to GitHub and open the{' '}
            <a href={issueUrl} target="_blank" rel="noopener noreferrer">trade-profile issue template</a>.
            Once a maintainer approves it, a workflow commits your entry and it shows up here.
          </p>
        </div>
      )}

      {!demoEnabled && loadState === 'ready' && hasPublished && matches.length === 0 && (
        <div className="card card-pad muted" style={{ textAlign: 'center' }}>
          {publishedUsers.length} published profile{publishedUsers.length === 1 ? '' : 's'}, but none overlap with your duplicates and missing list at the current filters. Try widening distance or lowering min score, or mark more stickers as duplicates.
        </div>
      )}

      {demoEnabled && matches.length === 0 && (
        <div className="card card-pad muted" style={{ textAlign: 'center' }}>
          Demo mode: no matches at the current filters. Mark some stickers as duplicates (count &gt; 1) and add what you're missing to start matching.
        </div>
      )}

      {matches.length > 0 && (
        <div className="trade-card">
          {demoEnabled && (
            <div className="demo-banner">
              Developer demo mode: the collectors below are generated test profiles used to demonstrate scoring. They are not real accounts.
            </div>
          )}
          {matches.slice(0, 24).map(m => (
            <TradeRow
              key={m.user.id}
              match={m}
              demoMode={demoEnabled}
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

function TradeRow({ match, demoMode, expanded, accepted, onToggleExpand, onToggleAccept }: {
  match: TradeMatch; demoMode: boolean; expanded: boolean; accepted: boolean; onToggleExpand: () => void; onToggleAccept: () => void;
}) {
  const { user, iCanGive, iCanReceive, score, components, distanceLabel } = match;
  const initials = user.alias.split(' ').map(s => s[0]).slice(0, 2).join('').toUpperCase();
  const sourceLabel = demoMode
    ? 'Demo collector'
    : user.handle
      ? `via @${user.handle} on GitHub`
      : 'Published profile';

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
          {sourceLabel} · {distanceLabel} · {user.completionPct}% complete
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
              {demoMode
                ? 'This is generated demo data, not a real account.'
                : 'To reach this collector, comment on their original trade-profile issue on GitHub. The site never exposes email addresses or precise locations.'}
            </div>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gap: 8, justifyItems: 'end' }}>
        <div className="trade-score" aria-label={`Score ${score}`}>{score}</div>
        <button className="btn btn-sm" onClick={onToggleExpand}>{expanded ? 'Hide details' : 'Why this match?'}</button>
        <button className={`btn btn-sm ${accepted ? '' : 'btn-primary'}`} onClick={onToggleAccept}>
          {accepted ? 'Marked ✓' : demoMode ? 'Test demo trade' : 'Mark as interested'}
        </button>
      </div>
    </div>
  );
}
