// Loader for the GitHub-only static trade network database.
// The frontend reads `public/trade-network.json` (deployed alongside the bundle).
// Writes happen exclusively via GitHub Issues + the process-trade-profile workflow.

import type { SimUser } from '../types';
import { REGION_PRESETS } from './geo';

export interface PublishedProfile {
  id: string;
  alias: string;
  region: string;
  submittedBy: string;
  submittedAt: string;
  sourceIssue: number;
  missingIds: number[];
  duplicates: Record<string, number>;
  completionPct: number;
}

export interface TradeNetworkDB {
  version: number;
  generatedAt: string;
  source: string;
  notes?: string;
  profiles: PublishedProfile[];
}

const REGION_COORDS = new Map(REGION_PRESETS.map(r => [r.label, r.coords]));

// Fallback coords for "Other / prefer not to say": antipode-ish placeholder so
// distance scoring gives the lowest weight without crashing.
const UNKNOWN_COORDS = { lat: 0, lng: 0 };

export function profileToSimUser(p: PublishedProfile, catalogTotal: number): SimUser {
  const coords = REGION_COORDS.get(p.region) ?? UNKNOWN_COORDS;
  const ownedIds: number[] = [];
  const dupIds = new Set(Object.keys(p.duplicates).map(Number));
  const missing = new Set(p.missingIds);
  for (let id = 1; id <= catalogTotal; id++) {
    if (!missing.has(id)) ownedIds.push(id);
  }
  // Duplicates imply ownership; make sure they are included.
  for (const id of dupIds) if (!missing.has(id) && !ownedIds.includes(id)) ownedIds.push(id);

  const daysAgo = Math.max(0, Math.round(
    (Date.now() - new Date(p.submittedAt).getTime()) / 86_400_000,
  ));

  return {
    id: p.id,
    handle: p.submittedBy,
    alias: p.alias,
    region: p.region,
    coords,
    confedFavorite: '',
    ownedIds,
    duplicates: p.duplicates,
    completionPct: p.completionPct,
    lastActiveDaysAgo: daysAgo,
  };
}

export async function loadTradeNetwork(baseUrl: string): Promise<TradeNetworkDB> {
  // baseUrl is import.meta.env.BASE_URL — works for "./" (user pages) and "/repo/" (project pages).
  const url = new URL('trade-network.json', new URL(baseUrl, window.location.href)).toString();
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`Failed to fetch trade-network.json (${res.status})`);
  const db = await res.json();
  if (!db || typeof db !== 'object' || !Array.isArray(db.profiles)) {
    throw new Error('trade-network.json: invalid shape');
  }
  return db as TradeNetworkDB;
}

export function buildIssueUrl(repoSlug: string | undefined): string {
  // If repoSlug is missing, point at the generic new-issue page (will fall back
  // to a chooser on the repo). Used in the UI to deep-link the issue form.
  const slug = repoSlug || 'OWNER/REPO';
  return `https://github.com/${slug}/issues/new?template=trade-profile.yml`;
}

export function buildRemovalUrl(repoSlug: string | undefined): string {
  const slug = repoSlug || 'OWNER/REPO';
  return `https://github.com/${slug}/issues/new?template=remove-trade-profile.yml`;
}
