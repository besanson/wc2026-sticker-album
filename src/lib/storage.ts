// Client-side persistence — works on GitHub Pages with no backend.
// Designed so the same shape can later be synced through a serverless function
// (e.g. /api/sync) or a GitHub Gist; the storage interface stays the same.
import type { PersistedState } from '../types';

const KEY = 'wc2026-album:v1';

const DEFAULTS: PersistedState = {
  version: 1,
  profile: null,
  album: {},
  theme: 'system',
  packsPurchased: 0,
  proposedTradeAcceptances: [],
};

export function loadState(): PersistedState {
  if (typeof window === 'undefined') return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw);
    if (parsed?.version === 1) return { ...DEFAULTS, ...parsed };
  } catch {
    /* ignore */
  }
  return DEFAULTS;
}

export function saveState(state: PersistedState) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* quota — silently no-op */
  }
}

export function clearState() {
  if (typeof window === 'undefined') return;
  try { window.localStorage.removeItem(KEY); } catch { /* */ }
}
