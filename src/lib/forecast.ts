// Completion forecast — Monte Carlo over uniform pack draws (no per-sticker rarity tiers since the
// official Panini distribution isn't published; assumption is documented in the UI).
// Inputs: total stickers, owned set, planned packs, stickers per pack, and any committed trades.
import type { AlbumState, Catalog } from '../types';

export interface ForecastResult {
  trials: number;
  perTrialCompletionPct: number[];     // sorted ascending
  mean: number;
  median: number;
  p10: number;
  p90: number;
  pComplete: number;
  expectedDuplicates: number;
  expectedSpendUSD: number;
}

// Simple seeded RNG — deterministic per run for stable visuals.
function mulberry32(seed: number) {
  return () => {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface ForecastInput {
  catalog: Catalog;
  album: AlbumState;
  plannedPacks: number;
  tradedIn: number[];  // sticker ids you'll acquire via accepted trades (will count as owned)
  tradedOut: number[]; // sticker ids you'll give from your duplicates
  trials?: number;
  seed?: number;
}

export function forecast({ catalog, album, plannedPacks, tradedIn, tradedOut, trials = 800, seed = 42 }: ForecastInput): ForecastResult {
  const total = catalog.total;
  const allIds: number[] = [];
  for (const s of catalog.sections) for (const st of s.stickers) allIds.push(st.id);

  // Owned-after-trades starting set.
  const tradedInSet = new Set(tradedIn);
  const tradedOutSet = new Set(tradedOut);
  // Pre-compute current counts after trades.
  const baseCounts: Record<number, number> = {};
  for (const id of allIds) baseCounts[id] = album[id] ?? 0;
  for (const id of tradedInSet) baseCounts[id] = (baseCounts[id] ?? 0) + 1;
  for (const id of tradedOutSet) {
    if ((baseCounts[id] ?? 0) > 1) baseCounts[id] -= 1; // can only trade out a duplicate
  }

  const stickersPerPack = catalog.stickersPerPack;
  const draws = plannedPacks * stickersPerPack;

  const rng = mulberry32(seed);
  const completions: number[] = [];
  let completeCount = 0;
  let totalDuplicatesAcrossTrials = 0;

  for (let t = 0; t < trials; t++) {
    // Clone counts
    const counts: Record<number, number> = { ...baseCounts };
    for (let i = 0; i < draws; i++) {
      // Uniform draw — assumption documented in UI.
      const id = allIds[Math.floor(rng() * allIds.length)];
      counts[id] = (counts[id] ?? 0) + 1;
    }
    let owned = 0;
    let dupes = 0;
    for (const id of allIds) {
      const c = counts[id] ?? 0;
      if (c >= 1) owned += 1;
      if (c > 1) dupes += c - 1;
    }
    const pct = owned / total;
    completions.push(pct);
    totalDuplicatesAcrossTrials += dupes;
    if (owned === total) completeCount += 1;
  }

  completions.sort((a, b) => a - b);
  const pct = (q: number) => completions[Math.min(completions.length - 1, Math.floor(q * completions.length))];

  const mean = completions.reduce((a, b) => a + b, 0) / completions.length;
  const median = pct(0.5);
  const p10 = pct(0.1);
  const p90 = pct(0.9);
  const expectedDuplicates = totalDuplicatesAcrossTrials / trials;
  const expectedSpendUSD = plannedPacks * catalog.retailPackPriceUSD;

  return {
    trials,
    perTrialCompletionPct: completions,
    mean: mean * 100,
    median: median * 100,
    p10: p10 * 100,
    p90: p90 * 100,
    pComplete: completeCount / trials,
    expectedDuplicates,
    expectedSpendUSD,
  };
}

// Analytic helper — coupon-collector style expected packs to complete from scratch (uniform draws),
// shown alongside the simulation as a sanity baseline.
export function expectedPacksToComplete(catalog: Catalog, currentlyOwned: number): number {
  const N = catalog.total;
  let expectedDraws = 0;
  for (let k = currentlyOwned; k < N; k++) {
    expectedDraws += N / (N - k);
  }
  return expectedDraws / catalog.stickersPerPack;
}
