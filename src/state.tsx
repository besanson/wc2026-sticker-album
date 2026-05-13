import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { AlbumState, Catalog, PersistedState, Profile, SimUser } from './types';
import { loadState, saveState, clearState } from './lib/storage';
import catalogJson from './data/catalog.json';
import usersJson from './data/users.json';

const catalog = catalogJson as unknown as Catalog;
const simUsers = (usersJson as unknown as { users: SimUser[] }).users;

interface Ctx {
  catalog: Catalog;
  users: SimUser[];
  profile: Profile | null;
  album: AlbumState;
  packsPurchased: number;
  proposedTradeAcceptances: string[];
  theme: 'light' | 'dark' | 'system';
  resolvedTheme: 'light' | 'dark';
  setProfile: (p: Profile | null) => void;
  setStickerCount: (id: number, count: number) => void;
  bulkSetSection: (sectionName: string, action: 'own-all' | 'unown-all') => void;
  setPacksPurchased: (n: number) => void;
  toggleTradeAcceptance: (userId: string) => void;
  setTheme: (t: 'light' | 'dark' | 'system') => void;
  clearAll: () => void;
}

const StateCtx = createContext<Ctx | null>(null);

function getSystemTheme(): 'light' | 'dark' {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function StateProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<PersistedState>(() => loadState());
  const [systemTheme, setSystemTheme] = useState<'light' | 'dark'>(() => getSystemTheme());

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mql = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => setSystemTheme(mql.matches ? 'dark' : 'light');
    mql.addEventListener?.('change', onChange);
    return () => mql.removeEventListener?.('change', onChange);
  }, []);

  // Persist
  useEffect(() => { saveState(state); }, [state]);

  const resolvedTheme = state.theme === 'system' ? systemTheme : state.theme;
  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('dark', resolvedTheme === 'dark');
  }, [resolvedTheme]);

  const setProfile = useCallback((p: Profile | null) => setState(s => ({ ...s, profile: p })), []);
  const setStickerCount = useCallback((id: number, count: number) => {
    setState(s => {
      const next = { ...s.album };
      if (count <= 0) delete next[id]; else next[id] = count;
      return { ...s, album: next };
    });
  }, []);
  const bulkSetSection = useCallback((sectionName: string, action: 'own-all' | 'unown-all') => {
    const section = catalog.sections.find(sec => sec.name === sectionName);
    if (!section) return;
    setState(s => {
      const next = { ...s.album };
      for (const st of section.stickers) {
        if (action === 'own-all') next[st.id] = Math.max(1, next[st.id] ?? 0);
        else delete next[st.id];
      }
      return { ...s, album: next };
    });
  }, []);
  const setPacksPurchased = useCallback((n: number) => setState(s => ({ ...s, packsPurchased: Math.max(0, Math.min(2000, Math.floor(n))) })), []);
  const toggleTradeAcceptance = useCallback((userId: string) => {
    setState(s => {
      const set = new Set(s.proposedTradeAcceptances);
      if (set.has(userId)) set.delete(userId); else set.add(userId);
      return { ...s, proposedTradeAcceptances: [...set] };
    });
  }, []);
  const setTheme = useCallback((t: 'light' | 'dark' | 'system') => setState(s => ({ ...s, theme: t })), []);
  const clearAll = useCallback(() => {
    clearState();
    setState({ version: 1, profile: null, album: {}, theme: 'system', packsPurchased: 0, proposedTradeAcceptances: [] });
  }, []);

  const value = useMemo<Ctx>(() => ({
    catalog,
    users: simUsers,
    profile: state.profile,
    album: state.album,
    packsPurchased: state.packsPurchased,
    proposedTradeAcceptances: state.proposedTradeAcceptances,
    theme: state.theme,
    resolvedTheme,
    setProfile, setStickerCount, bulkSetSection, setPacksPurchased,
    toggleTradeAcceptance, setTheme, clearAll,
  }), [state, resolvedTheme, setProfile, setStickerCount, bulkSetSection, setPacksPurchased, toggleTradeAcceptance, setTheme, clearAll]);

  return <StateCtx.Provider value={value}>{children}</StateCtx.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(StateCtx);
  if (!ctx) throw new Error('useApp must be used inside StateProvider');
  return ctx;
}

// Derived helpers — pure.
export function albumStats(album: AlbumState, catalog: Catalog) {
  let owned = 0, duplicates = 0, totalCounts = 0;
  for (const s of catalog.sections) for (const st of s.stickers) {
    const c = album[st.id] ?? 0;
    if (c >= 1) owned += 1;
    if (c > 1) duplicates += c - 1;
    totalCounts += c;
  }
  return {
    owned,
    missing: catalog.total - owned,
    duplicates,
    totalCounts,
    completionPct: catalog.total ? (owned / catalog.total) * 100 : 0,
  };
}
