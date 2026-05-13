// Trade matching: pair my duplicates with their missing, and their duplicates with my missing.
// Score is explainable — every component is surfaced in the UI.
import type { AlbumState, Catalog, SimUser } from '../types';
import { distanceBucket, haversineKm } from './geo';

export interface TradeMatch {
  user: SimUser;
  distanceKm: number;
  distanceLabel: string;
  iCanGive: number[];     // sticker ids I have as duplicates that they need
  iCanReceive: number[];  // sticker ids they have as duplicates that I need
  score: number;
  components: {
    overlap: number;      // 0..1 raw min(give, receive) / 20
    balance: number;      // 0..1 how even the trade is
    distance: number;     // 0..1 multiplier
    activity: number;     // 0..1 recency multiplier
  };
}

export function myDuplicates(album: AlbumState): number[] {
  return Object.entries(album)
    .filter(([, c]) => (c as number) > 1)
    .map(([id]) => Number(id));
}

export function myMissing(album: AlbumState, catalog: Catalog): number[] {
  const missing: number[] = [];
  for (const s of catalog.sections) for (const st of s.stickers) {
    if (!album[st.id] || album[st.id] < 1) missing.push(st.id);
  }
  return missing;
}

export function findTrades(
  album: AlbumState,
  catalog: Catalog,
  users: SimUser[],
  myCoords: { lat: number; lng: number } | undefined,
  options: { maxDistanceKm?: number; minScore?: number } = {}
): TradeMatch[] {
  const dupIds = new Set(myDuplicates(album));
  const missingIds = new Set(myMissing(album, catalog));
  const matches: TradeMatch[] = [];

  for (const u of users) {
    const theirOwned = new Set(u.ownedIds);
    const theirDupSet = new Set(Object.keys(u.duplicates).map(Number));

    // Stickers I can give them: my duplicates AND they don't own.
    const iCanGive: number[] = [];
    for (const id of dupIds) if (!theirOwned.has(id)) iCanGive.push(id);

    // Stickers they can give me: their duplicates AND I'm missing.
    const iCanReceive: number[] = [];
    for (const id of theirDupSet) if (missingIds.has(id)) iCanReceive.push(id);

    if (iCanGive.length === 0 && iCanReceive.length === 0) continue;

    // Distance
    const distanceKm = myCoords
      ? haversineKm(myCoords, u.coords)
      : 9999;
    const bucket = distanceBucket(distanceKm);
    if (options.maxDistanceKm && distanceKm > options.maxDistanceKm) continue;

    // Scoring components
    const overlap = Math.min(1, (Math.min(iCanGive.length, iCanReceive.length) + 0.5 * Math.max(iCanGive.length, iCanReceive.length)) / 20);
    const balance = (iCanGive.length + iCanReceive.length === 0)
      ? 0
      : 1 - Math.abs(iCanGive.length - iCanReceive.length) / (iCanGive.length + iCanReceive.length + 1);
    const distance = bucket.weight;
    const activity = Math.max(0.4, 1 - u.lastActiveDaysAgo / 30);

    // Weighted average — sticker overlap is the primary signal.
    const score = Math.round(
      100 * (0.55 * overlap + 0.20 * balance + 0.18 * distance + 0.07 * activity)
    );
    if (options.minScore && score < options.minScore) continue;

    matches.push({
      user: u,
      distanceKm,
      distanceLabel: bucket.label,
      iCanGive,
      iCanReceive,
      score,
      components: { overlap, balance, distance, activity },
    });
  }

  matches.sort((a, b) => b.score - a.score);
  return matches;
}
