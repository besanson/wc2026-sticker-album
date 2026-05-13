import { useMemo, useState } from 'react';
import { useApp, albumStats } from '../state';
import type { Section, Sticker } from '../types';
import { SearchIcon, CheckIcon, MinusIcon, PlusIcon, CloseIcon } from './Icons';

type Filter = 'all' | 'owned' | 'missing' | 'dup';

export function AlbumView() {
  const { catalog, album, setStickerCount, bulkSetSection } = useApp();
  const [filter, setFilter] = useState<Filter>('all');
  const [query, setQuery] = useState('');
  const [confed, setConfed] = useState<string>('all');
  const [openId, setOpenId] = useState<number | null>(null);

  const confedOptions = useMemo(() => {
    const set = new Set<string>();
    for (const s of catalog.sections) if (s.team) set.add(s.team.confed);
    return ['all', ...[...set].sort()];
  }, [catalog]);

  const stats = albumStats(album, catalog);

  const filteredSections = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out: Section[] = [];
    for (const sec of catalog.sections) {
      if (confed !== 'all' && (!sec.team || sec.team.confed !== confed)) continue;
      const stickers = sec.stickers.filter(st => {
        const c = album[st.id] ?? 0;
        if (filter === 'owned' && !(c >= 1)) return false;
        if (filter === 'missing' && c >= 1) return false;
        if (filter === 'dup' && !(c > 1)) return false;
        if (!q) return true;
        return (
          st.label.toLowerCase().includes(q) ||
          st.code.toLowerCase().includes(q) ||
          sec.name.toLowerCase().includes(q)
        );
      });
      if (stickers.length === 0) continue;
      out.push({ ...sec, stickers });
    }
    return out;
  }, [catalog, album, filter, query, confed]);

  const openSticker = openId !== null ? findSticker(catalog.sections, openId) : null;

  return (
    <div className="stack-lg">
      <header className="card card-pad">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>Album</h2>
            <div className="sub">{catalog.edition}</div>
          </div>
          <div className="row gap-3" style={{ flexWrap: 'wrap' }}>
            <Kpi label="Owned" value={`${stats.owned}`} sub={`${stats.completionPct.toFixed(1)}%`} />
            <Kpi label="Missing" value={`${stats.missing}`} />
            <Kpi label="Duplicates" value={`${stats.duplicates}`} />
            <Kpi label="Total" value={`${catalog.total}`} />
          </div>
        </div>
        <div className="progress-track mt-4" aria-label="album completion">
          <div className="progress-fill" style={{ width: `${stats.completionPct.toFixed(2)}%` }} />
        </div>
      </header>

      <div className="album-controls">
        <div className="field" style={{ position: 'relative' }}>
          <label className="visually-hidden" htmlFor="search">Search stickers</label>
          <input
            id="search"
            className="input"
            placeholder="Search team, player, code…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            style={{ paddingLeft: 36 }}
          />
          <span style={{ position: 'absolute', left: 12, top: 10, color: 'var(--text-faint)' }}>
            <SearchIcon size={18} />
          </span>
        </div>
        <select className="select" value={confed} onChange={e => setConfed(e.target.value)} aria-label="Confederation">
          {confedOptions.map(c => <option key={c} value={c}>{c === 'all' ? 'All confederations' : c}</option>)}
        </select>
        <div className="filter-row" role="tablist" aria-label="Status filter">
          {(['all','owned','missing','dup'] as Filter[]).map(f => (
            <button
              key={f}
              className="chip"
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
            >
              {f === 'owned' && <span className="dot owned" />}
              {f === 'dup' && <span className="dot dup" />}
              {f === 'missing' && <span className="dot missing" />}
              {f === 'all' ? 'All' : f === 'dup' ? 'Doubles' : f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {filteredSections.length === 0 ? (
        <div className="card card-pad muted" style={{ textAlign: 'center' }}>
          No stickers match. Try clearing filters.
        </div>
      ) : filteredSections.map(sec => (
        <section key={sec.name} className="section-block">
          <header className="section-head">
            <h3>
              {sec.name}
              {sec.team && <span className="count">· {sec.team.confed}{sec.team.host ? ' · Host' : ''}</span>}
              <span className="count">·&nbsp;{ownedInSection(sec, album)}/{sec.stickers.length}</span>
            </h3>
            <div className="row gap-2">
              <button className="btn btn-sm" onClick={() => bulkSetSection(sec.name, 'own-all')}>Mark all owned</button>
              <button className="btn btn-sm btn-ghost" onClick={() => bulkSetSection(sec.name, 'unown-all')}>Reset</button>
            </div>
          </header>
          <div className="sticker-grid" role="list">
            {sec.stickers.map(st => {
              const c = album[st.id] ?? 0;
              const state = c === 0 ? 'missing' : c > 1 ? 'dup' : 'owned';
              return (
                <button
                  role="listitem"
                  key={st.id}
                  className="sticker"
                  data-state={state}
                  onClick={() => setOpenId(st.id)}
                  aria-label={`${st.label} · ${st.code} · ${state === 'owned' ? 'owned' : state === 'dup' ? `owned + ${c - 1} duplicate${c-1>1?'s':''}` : 'missing'}`}
                >
                  <span className="num">#{st.id}</span>
                  <span className="glyph">{stickerGlyph(st)}</span>
                  <span className="lbl">{shortLabel(st)}</span>
                  {state === 'dup' && <span className="badge">×{c}</span>}
                  {state === 'owned' && <span className="badge" style={{ background: 'var(--accent)', color: '#fff' }}>✓</span>}
                </button>
              );
            })}
          </div>
        </section>
      ))}

      {openSticker && (
        <StickerSheet sticker={openSticker} count={album[openSticker.id] ?? 0} onClose={() => setOpenId(null)} onChange={n => setStickerCount(openSticker.id, n)} />
      )}
    </div>
  );
}

function shortLabel(st: Sticker) {
  if (st.kind === 'player') return `${st.team?.code} ${st.label}`;
  if (st.kind === 'badge' && st.team) return st.team.name;
  return st.label;
}

function stickerGlyph(st: Sticker) {
  if (st.team) return st.team.code;
  switch (st.kind) {
    case 'trophy': return '◈';
    case 'logo': return '✦';
    case 'mascot': return '☺';
    case 'ball': return '◯';
    case 'poster': return '▥';
    case 'city': return '⌂';
    case 'legend': return '★';
    default: return '⬡';
  }
}

function ownedInSection(sec: Section, album: Record<number, number>) {
  let n = 0;
  for (const st of sec.stickers) if ((album[st.id] ?? 0) >= 1) n++;
  return n;
}

function findSticker(sections: Section[], id: number): Sticker | null {
  for (const s of sections) for (const st of s.stickers) if (st.id === id) return st;
  return null;
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ minWidth: 70 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</div>
      <div className="tabular" style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 22, lineHeight: 1.1 }}>{value}</div>
      {sub && <div className="muted" style={{ fontSize: 11 }}>{sub}</div>}
    </div>
  );
}

function StickerSheet({ sticker, count, onClose, onChange }: { sticker: Sticker; count: number; onClose: () => void; onChange: (n: number) => void }) {
  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label={`${sticker.label} details`}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head">
          <div className="preview">
            {sticker.team ? sticker.team.code : '✦'}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>#{sticker.id} · {sticker.code}</div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: 19, fontWeight: 700 }}>{sticker.label}</div>
            <div className="muted" style={{ fontSize: 13 }}>{sticker.section}{sticker.team ? ` · ${sticker.team.confed}` : ''}</div>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close"><CloseIcon /></button>
        </div>
        <div className="field">
          <label>Copies you have</label>
          <div className="qty-row">
            <button className="qty-btn" onClick={() => onChange(Math.max(0, count - 1))} aria-label="Decrease"><MinusIcon size={16}/></button>
            <div className="qty-display" aria-live="polite">{count}</div>
            <button className="qty-btn" onClick={() => onChange(count + 1)} aria-label="Increase"><PlusIcon size={16}/></button>
          </div>
          <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
            {count === 0 && 'Missing — add it to your wishlist by leaving it at zero.'}
            {count === 1 && 'Owned. Add another copy if you pulled a duplicate.'}
            {count > 1 && `Owned + ${count - 1} duplicate${count - 1 > 1 ? 's' : ''} — eligible for trade.`}
          </div>
        </div>
        <div className="modal-row">
          <button className="btn" onClick={() => { onChange(0); onClose(); }}>Mark missing</button>
          <button className="btn btn-primary" onClick={() => { onChange(Math.max(1, count)); onClose(); }}><CheckIcon size={16}/>&nbsp;Mark owned</button>
        </div>
      </div>
    </div>
  );
}
