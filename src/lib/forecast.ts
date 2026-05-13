// Completion forecast. The default mode is a practical "collated packs" model:
// early packs are less duplicate-heavy than independent random draws, reflecting
// real-world sticker box collation observed by collectors. A pure uniform model
// is still available as a conservative baseline.
// Inputs: total stickers, owned set, planned packs, stickers per pack, and any committed trades.
import type { AlbumState, Catalog } from '../types';

export interface ForecastResult {
  trials: number;
  perTrialCompletionPct: number[];     // sorted ascending, 0–100
  mean: number;
  median: number;
  p10: number;
  p90: number;
  pComplete: number;
  expectedDuplicates: number;
  expectedMissing: number;
  expectedSpendUSD: number;
  startingOwned: number;
  startingMissing: number;
  draws: number;
  model: ForecastModel;
  collationFactor: number;
  observedDuplicateRate: number | null;
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
  model?: ForecastModel;
  collationFactor?: number;
  trials?: number;
  seed?: number;
}

export type ForecastModel = 'collated' | 'uniform';

function expectedRepeatRateFromScratch(total: number, draws: number, collationFactor: number): number {
  if (draws <= 0) return 0;
  let owned = 0;
  let duplicates = 0;
  for (let i = 0; i < draws; i++) {
    const missingShare = Math.max(0, (total - owned) / total);
    const probabilityNew = owned === 0 ? 1 : Math.min(0.995, collationFactor * missingShare);
    owned += probabilityNew;
    duplicates += (1 - probabilityNew);
  }
  return duplicates / draws;
}

export function calibrateCollationFactor(total: number, stickersPerPack: number, observedPacks: number, observedRepeatRate: number): number {
  const draws = Math.max(0, Math.floor(observedPacks)) * stickersPerPack;
  if (draws <= 0) return 1.7;
  const target = Math.max(0, Math.min(0.95, observedRepeatRate));

  let lo = 0.25;
  let hi = 3.5;
  for (let i = 0; i < 32; i++) {
    const mid = (lo + hi) / 2;
    const rate = expectedRepeatRateFromScratch(total, draws, mid);
    // Higher collation factor means more new stickers and fewer repeats.
    if (rate > target) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

export function forecast({
  catalog,
  album,
  plannedPacks,
  tradedIn,
  tradedOut,
  model = 'collated',
  collationFactor = 1.7,
  trials = 800,
  seed = 42
}: ForecastInput): ForecastResult {
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

  let startingOwned = 0;
  let startingDuplicateCount = 0;
  let startingTotalStickers = 0;
  for (const id of allIds) {
    const c = baseCounts[id] ?? 0;
    startingTotalStickers += c;
    if (c >= 1) startingOwned += 1;
    if (c > 1) startingDuplicateCount += c - 1;
  }
  const observedDuplicateRate = startingTotalStickers > 0 ? startingDuplicateCount / startingTotalStickers : null;

  const stickersPerPack = catalog.stickersPerPack;
  const draws = plannedPacks * stickersPerPack;

  const rng = mulberry32(seed);
  const completions: number[] = [];
  let completeCount = 0;
  let totalDuplicatesAcrossTrials = 0;
  let totalMissingAcrossTrials = 0;

  for (let t = 0; t < trials; t++) {
    const ownedIds: number[] = [];
    const missingIds: number[] = [];
    const missingSet = new Set<number>();
    let dupes = startingDuplicateCount;
    for (const id of allIds) {
      if ((baseCounts[id] ?? 0) >= 1) ownedIds.push(id);
      else {
        missingIds.push(id);
        missingSet.add(id);
      }
    }

    for (let i = 0; i < draws; i++) {
      if (missingIds.length === 0) {
        dupes += 1;
        continue;
      }

      if (model === 'collated') {
        // Real packs are not equivalent to a global random number generator.
        // This raises the chance of a new sticker early, then naturally falls
        // as the album fills. A factor around 1.7 matches the user's observed
        // ~12% repeat rate after roughly 110 packs from a cold start.
        const missingShare = missingIds.length / total;
        const probabilityNew = ownedIds.length === 0 ? 1 : Math.min(0.995, collationFactor * missingShare);
        if (rng() < probabilityNew) {
          const idx = Math.floor(rng() * missingIds.length);
          const id = missingIds[idx];
          missingIds[idx] = missingIds[missingIds.length - 1];
          missingIds.pop();
          ownedIds.push(id);
        } else {
          dupes += 1;
        }
      } else {
        const id = allIds[Math.floor(rng() * allIds.length)];
        if (missingSet.has(id)) {
          missingSet.delete(id);
          ownedIds.push(id);
        } else {
          dupes += 1;
        }
      }
    }
    const owned = ownedIds.length;
    const pct = owned / total;
    completions.push(pct);
    totalDuplicatesAcrossTrials += dupes;
    totalMissingAcrossTrials += (total - owned);
    if (owned === total) completeCount += 1;
  }

  completions.sort((a, b) => a - b);
  const pct = (q: number) => completions[Math.min(completions.length - 1, Math.floor(q * completions.length))];

  const mean = completions.reduce((a, b) => a + b, 0) / completions.length;
  const median = pct(0.5);
  const p10 = pct(0.1);
  const p90 = pct(0.9);
  const expectedDuplicates = totalDuplicatesAcrossTrials / trials;
  const expectedMissing = totalMissingAcrossTrials / trials;
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
    expectedMissing,
    expectedSpendUSD,
    startingOwned,
    startingMissing: total - startingOwned,
    draws,
    model,
    collationFactor,
    observedDuplicateRate,
  };
}

// Analytic helper — expected packs to complete from the current point,
// shown alongside the simulation as a sanity baseline.
export function expectedPacksToComplete(catalog: Catalog, currentlyOwned: number, model: ForecastModel = 'collated', collationFactor = 1.7): number {
  const N = catalog.total;
  let expectedDraws = 0;
  for (let k = currentlyOwned; k < N; k++) {
    const missingShare = (N - k) / N;
    const probabilityNew = model === 'collated'
      ? (k === 0 ? 1 : Math.min(0.995, collationFactor * missingShare))
      : missingShare;
    expectedDraws += 1 / Math.max(probabilityNew, 1 / N);
  }
  return expectedDraws / catalog.stickersPerPack;
}
