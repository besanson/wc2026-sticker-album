export type StickerKind =
  | 'badge' | 'team-photo' | 'lineup' | 'player' | 'legend'
  | 'trophy' | 'logo' | 'mascot' | 'ball' | 'poster' | 'city'
  | 'slogan' | 'host' | 'museum';

export interface TeamMeta {
  code: string;
  name: string;
  confed: string;
  host: boolean;
}

export interface Sticker {
  id: number;
  code: string;
  kind: StickerKind;
  label: string;
  section: string;
  team: TeamMeta | null;
}

export interface Section {
  name: string;
  kind: 'team' | 'special';
  team?: TeamMeta;
  stickers: Sticker[];
}

export interface Catalog {
  edition: string;
  generatedAt: string;
  source: string;
  total: number;
  stickersPerPack: number;
  retailPackPriceUSD: number;
  sections: Section[];
}

export interface SimUser {
  id: string;
  handle: string;
  alias: string;
  region: string;
  coords: { lat: number; lng: number };
  confedFavorite: string;
  ownedIds: number[];
  duplicates: Record<string, number>;
  completionPct: number;
  lastActiveDaysAgo: number;
}

export interface Profile {
  alias: string;
  email: string;            // stored locally only; never leaves the device unless backend is wired
  region: string;           // coarse: city, country or country-only
  coords?: { lat: number; lng: number }; // optional, rounded to 0.5°
  consentAt: string;        // ISO timestamp
  shareForTrades: boolean;  // explicit consent to include in trade matching
  createdAt: string;
}

export type AlbumState = Record<number, number>; // stickerId -> count (0 = missing, 1 = owned, >1 = duplicate)

export interface PersistedState {
  version: 1;
  profile: Profile | null;
  album: AlbumState;
  theme: 'light' | 'dark' | 'system';
  packsPurchased: number;
  proposedTradeAcceptances: string[]; // user ids whose trade you've accepted (in this client session simulation)
}
